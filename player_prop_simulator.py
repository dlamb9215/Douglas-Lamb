"""Volume-based player projections and reproducible prop simulations.

Inputs are supplied by the analyst; this module does not fetch live rosters,
injuries, player usage, or sportsbook lines. Only confirmed active starters
are eligible for a projection.
"""
import math
import random

from player_projections import validate_projection_player, project_player_workload


def _number(name, value, low=0.0, high=None):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be numeric.")
    if not math.isfinite(value) or value < low or (high is not None and value > high):
        raise ValueError(f"{name} is outside its valid range.")
    return float(value)


def project_player_stats(player, workload, rates):
    """Convert projected opportunity and efficiency inputs into stat means.

    Required workload keys are those accepted by project_player_workload.
    Rates:
      QB: passing_attempts, completion_rate, yards_per_completion.
      RB: yards_per_carry; optional catch_rate, yards_per_reception.
      WR/TE: catch_rate, yards_per_reception.
    """
    validate_projection_player(player)
    if not isinstance(workload, dict) or not isinstance(rates, dict):
        raise ValueError("workload and rates must be dictionaries.")

    w = project_player_workload(
        player,
        projected_snaps=workload.get("projected_snaps", 0),
        projected_routes=workload.get("projected_routes", 0),
        projected_targets=workload.get("projected_targets", 0),
        projected_carries=workload.get("projected_carries", 0),
        red_zone_opportunities=workload.get("red_zone_opportunities", 0),
    )
    position = player["position"]
    stats = {"snaps": float(w["projected_snaps"])}

    if position == "QB":
        attempts = _number("passing_attempts", rates.get("passing_attempts"), 0, 75)
        completion_rate = _number("completion_rate", rates.get("completion_rate"), 0, 1)
        ypc = _number("yards_per_completion", rates.get("yards_per_completion"), 0, 30)
        completions = attempts * completion_rate
        stats.update({
            "passing_attempts": attempts,
            "completions": completions,
            "passing_yards": completions * ypc,
            "passing_tds": _number("passing_tds", rates.get("passing_tds", 0), 0, 10),
            "interceptions": _number("interceptions", rates.get("interceptions", 0), 0, 8),
            "rushing_attempts": float(w["projected_carries"]),
            "rushing_yards": float(w["projected_carries"]) * _number(
                "yards_per_carry", rates.get("yards_per_carry", 0), 0, 20
            ),
        })
    elif position == "RB":
        carries = float(w["projected_carries"])
        ypc = _number("yards_per_carry", rates.get("yards_per_carry"), 0, 20)
        targets = float(w["projected_targets"])
        catch_rate = _number("catch_rate", rates.get("catch_rate", 0), 0, 1)
        ypr = _number("yards_per_reception", rates.get("yards_per_reception", 0), 0, 40)
        stats.update({
            "carries": carries,
            "rushing_yards": carries * ypc,
            "targets": targets,
            "receptions": targets * catch_rate,
            "receiving_yards": targets * catch_rate * ypr,
        })
    elif position in {"WR", "TE"}:
        targets = float(w["projected_targets"])
        catch_rate = _number("catch_rate", rates.get("catch_rate"), 0, 1)
        ypr = _number("yards_per_reception", rates.get("yards_per_reception"), 0, 40)
        receptions = targets * catch_rate
        stats.update({
            "targets": targets,
            "receptions": receptions,
            "receiving_yards": receptions * ypr,
        })
    else:
        raise ValueError(f"Player prop projections are not supported for {position}.")

    stats["red_zone_opportunities"] = float(w["red_zone_opportunities"])
    return {
        "player": player["name"],
        "team": player["team"],
        "position": position,
        "workload": w,
        "projected_stats": {key: round(value, 2) for key, value in stats.items()},
        "data_note": "Analyst-supplied workload and efficiency assumptions; not live-verified.",
    }


def simulate_player_prop(projection, stat, line, trials=100000, seed=42,
                         standard_deviation=None):
    """Estimate over/under/push probability for one projected stat.

    Uses a normal approximation around the projected mean. Count-like stats
    are rounded to whole-number outcomes. Calibrate dispersion with historical
    player game logs before using probabilities as betting edges.
    """
    if not isinstance(projection, dict) or "projected_stats" not in projection:
        raise ValueError("A player projection result is required.")
    if stat not in projection["projected_stats"]:
        raise ValueError(f"Stat not available in projection: {stat}")
    if not isinstance(trials, int) or isinstance(trials, bool) or trials < 1:
        raise ValueError("trials must be a positive integer.")
    line = _number("line", line, 0)
    mean = float(projection["projected_stats"][stat])
    count_stats = {
        "passing_attempts", "completions", "passing_tds", "interceptions",
        "rushing_attempts", "carries", "targets", "receptions",
        "snaps", "red_zone_opportunities",
    }
    if standard_deviation is None:
        empirical_sd = projection["projected_stats"].get(stat + "_stddev")
        if isinstance(empirical_sd, (int, float)) and not isinstance(empirical_sd, bool) and empirical_sd > 0:
            sd = float(empirical_sd)
        else:
            sd = max(0.75, math.sqrt(max(mean, 0.0))) if stat in count_stats else max(1.0, mean * 0.25)
    else:
        sd = _number("standard_deviation", standard_deviation, 0.01, 1000)

    rng = random.Random(seed)
    over = under = push = 0
    samples = []
    for _ in range(trials):
        value = max(0.0, rng.gauss(mean, sd))
        if stat in count_stats:
            value = round(value)
        samples.append(value)
        if value > line:
            over += 1
        elif value < line:
            under += 1
        else:
            push += 1

    samples.sort()
    return {
        "player": projection["player"],
        "stat": stat,
        "line": line,
        "trials": trials,
        "seed": seed,
        "projected_mean": round(mean, 2),
        "simulated_mean": round(sum(samples) / trials, 2),
        "over_probability": round(over * 100.0 / trials, 2),
        "under_probability": round(under * 100.0 / trials, 2),
        "push_probability": round(push * 100.0 / trials, 2),
        "p05": round(samples[int((trials - 1) * 0.05)], 2),
        "p95": round(samples[int((trials - 1) * 0.95)], 2),
        "method_note": "Normal approximation; dispersion is provisional, not historically calibrated.",
    }


def project_from_recent_player_data(player):
    """Create a prop-simulation input from a live nflverse player-pool row.

    Uses recent per-game production as the baseline. It does not claim a
    matchup-adjusted forecast; callers should adjust volume/rates for opponent,
    role changes and expected game script before treating it as a projection.
    """
    from player_projections import validate_projection_player

    validate_projection_player(player)
    games = int(player.get("games", 0))
    if games < 1:
        raise ValueError("At least one recent game is required.")

    position = player["position"]
    stat_map = {
        "QB": ("passing_yards_per_game", "completions_per_game",
               "passing_attempts_per_game", "passing_tds_per_game",
               "interceptions_per_game", "rushing_yards_per_game",
               "carries_per_game"),
        "RB": ("carries_per_game", "rushing_yards_per_game",
               "targets_per_game", "receptions_per_game",
               "receiving_yards_per_game", "rushing_tds_per_game"),
        "WR": ("targets_per_game", "receptions_per_game",
               "receiving_yards_per_game", "receiving_tds_per_game"),
        "TE": ("targets_per_game", "receptions_per_game",
               "receiving_yards_per_game", "receiving_tds_per_game"),
    }
    if position not in stat_map:
        raise ValueError(f"Unsupported player position: {position}")

    stats = {}
    for key in stat_map[position]:
        stat_name = key.replace("_per_game", "")
        stats[stat_name] = round(float(player.get(key, 0) or 0), 2)
        sd_value = player.get(stat_name + "_stddev_per_game")
        if isinstance(sd_value, (int, float)) and not isinstance(sd_value, bool) and sd_value > 0:
            stats[stat_name + "_stddev"] = round(float(sd_value), 2)
    stats["games_in_sample"] = games
    stats["offense_snaps_per_game"] = player.get("offense_snaps_per_game")
    stats["offense_snap_pct_avg"] = player.get("offense_snap_pct_avg")
    stats["targets_per_game"] = round(float(player.get("targets_per_game", 0) or 0), 2)
    stats["carries_per_game"] = round(float(player.get("carries_per_game", 0) or 0), 2)

    return {
        "player": player["name"],
        "team": player["team"],
        "position": position,
        "projected_stats": stats,
        "data_note": (
            "Recent nflverse per-game baseline; not yet opponent-adjusted, "
            "not a confirmed game-day starter, and not a calibrated forecast."
        ),
    }
