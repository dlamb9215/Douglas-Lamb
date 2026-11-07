"""End-to-end NFL matchup player-prop analysis pipeline.

Consumes the refreshed nflverse player_pool.json and analyst-supplied prop
lines. It deliberately blocks missing/unverified teams and players. It does
not infer final game-day inactives from a depth chart.
"""
import argparse
import json
from datetime import datetime, timezone

from game_day_confirmations import validate_confirmation_file, confirmed_player_copy

from player_prop_simulator import (
    project_from_recent_player_data,
    simulate_player_prop,
)

SUPPORTED_STATS = {
    "QB": ("passing_yards", "completions", "passing_attempts",
           "passing_tds", "interceptions", "rushing_yards", "carries"),
    "RB": ("carries", "rushing_yards", "targets", "receptions",
           "receiving_yards", "rushing_tds"),
    "WR": ("targets", "receptions", "receiving_yards", "receiving_tds"),
    "TE": ("targets", "receptions", "receiving_yards", "receiving_tds"),
}


def load_player_pool(path="player_pool.json"):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("players"), list):
        raise ValueError("Player pool file has an invalid structure.")
    if not data.get("retrieved_at_utc") or not data.get("source"):
        raise ValueError("Player pool is missing source freshness metadata.")
    return data


def apply_opponent_adjustment(projection, player, home, away, team_records, shrink=0.35):
    """Apply a conservative opponent-allowed yardage adjustment to recent baselines."""
    if not team_records:
        projection["opponent_adjustment"] = {"applied": False, "reason": "Team defense dataset not supplied."}
        return projection
    records = {row.get("team"): row for row in team_records if isinstance(row, dict)}
    opponent = away if player.get("team") == home else home
    defense = records.get(opponent, {}).get("defense", {})
    league_values = {}
    for category in ("passing", "rushing"):
        values = [
            row.get("defense", {}).get(category, {}).get("yards_per_game")
            for row in records.values()
        ]
        values = [float(value) for value in values if isinstance(value, (int, float)) and value > 0]
        league_values[category] = sum(values) / len(values) if values else None
    factors = {}
    for category in ("passing", "rushing"):
        allowed = defense.get(category, {}).get("yards_per_game")
        average = league_values.get(category)
        if not isinstance(allowed, (int, float)) or not average:
            continue
        raw_ratio = float(allowed) / average
        factor = max(0.85, min(1.15, 1.0 + shrink * (raw_ratio - 1.0)))
        factors[category] = round(factor, 4)
    stats = projection.get("projected_stats", {})
    applied = {}
    qb_formula = None
    if player.get("position") == "QB":
        opponent_pass = defense.get("passing", {})
        allowed_yards = opponent_pass.get("yards_per_game")
        allowed_completions = opponent_pass.get("completions_per_game")
        player_completions = stats.get("completions")
        if (isinstance(allowed_yards, (int, float))
                and isinstance(allowed_completions, (int, float))
                and allowed_completions > 0
                and isinstance(player_completions, (int, float))):
            opponent_yards_per_completion = float(allowed_yards) / float(allowed_completions)
            qb_formula = float(player_completions) * opponent_yards_per_completion
            recent_baseline = stats.get("passing_yards", qb_formula)
            stats["passing_yards"] = round(0.5 * float(recent_baseline) + 0.5 * qb_formula, 2)
            applied["passing_yards_completion_formula"] = 0.5
        category_map = {"rushing_yards": "rushing"}
    elif player.get("position") == "RB":
        category_map = {"rushing_yards": "rushing", "receiving_yards": "passing"}
    else:
        category_map = {"receiving_yards": "passing"}
    for stat, category in category_map.items():
        factor = factors.get(category)
        if factor is None or stat not in stats:
            continue
        stats[stat] = round(float(stats[stat]) * factor, 2)
        sd_key = stat + "_stddev"
        if sd_key in stats:
            stats[sd_key] = round(float(stats[sd_key]) * factor, 2)
        applied[stat] = factor
    projection["opponent_adjustment"] = {
        "applied": bool(applied), "opponent": opponent,
        "factors": applied,
        "qb_completions_times_opponent_yards_per_completion": round(qb_formula, 2) if qb_formula is not None else None,
        "method": "QB passing yards blend 50% recent baseline with 50% completions x opponent yards/completion; other yardage uses 35% shrink toward league-average opponent yards allowed, capped at +/-15%. Provisional, not historically calibrated."
    }
    return projection


def analyze_matchup(home, away, player_pool, prop_lines=None,
                    trials=100000, seed=42, confirmations=None,
                    team_records=None):
    home, away = home.upper(), away.upper()
    if home == away:
        raise ValueError("Home and away teams must be different.")
    if trials < 1:
        raise ValueError("trials must be positive.")
    prop_lines = prop_lines or {}
    confirmations = confirmations or {}
    eligible = []
    blocked = []
    for player in player_pool["players"]:
        if player.get("team") not in {home, away}:
            continue
        if player.get("position") not in SUPPORTED_STATS:
            continue
        confirmed = confirmed_player_copy(player, confirmations)
        if confirmed is None:
            blocked.append({
                "player": player.get("name"),
                "team": player.get("team"),
                "reason": "No fresh official game-day confirmation of active status and starting role.",
            })
            continue
        eligible.append(confirmed)

    reports = []
    for index, player in enumerate(eligible):
        projection = project_from_recent_player_data(player)
        projection = apply_opponent_adjustment(
            projection, player, home, away, team_records
        )
        props = []
        for stat in SUPPORTED_STATS[player["position"]]:
            mean = projection["projected_stats"].get(stat)
            if mean is None:
                continue
            line_key = f"{player['team']}:{player['name']}:{stat}"
            line_input = prop_lines.get(line_key)
            item = {"stat": stat, "opponent_adjusted_projection": mean}
            if line_input is not None:
                if isinstance(line_input, dict):
                    line = float(line_input["line"])
                    over_odds = line_input.get("over_odds")
                    under_odds = line_input.get("under_odds")
                else:
                    line = float(line_input)
                    over_odds = under_odds = None
                simulation = simulate_player_prop(
                    projection, stat, line,
                    trials=trials, seed=seed + index,
                    standard_deviation=projection["projected_stats"].get(stat + "_stddev"),
                )
                item["simulation"] = simulation
                if over_odds is not None and under_odds is not None:
                    def implied(odds):
                        odds = float(odds)
                        if odds == 0:
                            raise ValueError("American odds cannot be zero.")
                        return 100.0 / (odds + 100.0) if odds > 0 else -odds / (-odds + 100.0)
                    over_raw, under_raw = implied(over_odds), implied(under_odds)
                    total_raw = over_raw + under_raw
                    over_fair, under_fair = over_raw / total_raw, under_raw / total_raw
                    def ev_per_100(probability, push_probability, odds):
                        profit = float(odds) if float(odds) > 0 else 10000.0 / -float(odds)
                        loss_probability = max(0.0, 1.0 - probability - push_probability)
                        return round(probability * profit - loss_probability * 100.0, 2)
                    decision_total = simulation["over_probability"] + simulation["under_probability"]
                    over_decision = simulation["over_probability"] / decision_total if decision_total else 0.0
                    under_decision = simulation["under_probability"] / decision_total if decision_total else 0.0
                    push_probability = simulation["push_probability"] / 100.0
                    item["market_comparison"] = {
                        "over_odds": over_odds, "under_odds": under_odds,
                        "vig_free_over_probability": round(over_fair * 100, 2),
                        "vig_free_under_probability": round(under_fair * 100, 2),
                        "over_edge_percentage_points": round(over_decision * 100 - over_fair * 100, 2),
                        "under_edge_percentage_points": round(under_decision * 100 - under_fair * 100, 2),
                        "over_expected_value_per_100": ev_per_100(simulation["over_probability"] / 100, push_probability, over_odds),
                        "under_expected_value_per_100": ev_per_100(simulation["under_probability"] / 100, push_probability, under_odds),
                    }
            props.append(item)
        reports.append({
            "player": player["name"],
            "team": player["team"],
            "position": player["position"],
            "games_in_sample": player.get("games"),
            "snap_count_per_game": player.get("offense_snaps_per_game"),
            "snap_percentage": player.get("offense_snap_pct_avg"),
            "recent_workload_baseline": {
                "snaps_per_game": player.get("offense_snaps_per_game"),
                "snap_share_pct": player.get("offense_snap_pct_avg"),
                "targets_per_game": player.get("targets_per_game"),
                "carries_per_game": player.get("carries_per_game"),
                "routes_per_game": None,
                "red_zone_opportunities_per_game": None,
                "unavailable_metrics_note": "Route participation and red-zone opportunity data are not included in the current player feed.",
            },
            "props": props,
            "data_note": projection["data_note"],
            "opponent_adjustment": projection.get("opponent_adjustment", {"applied": False}),
        })

    return {
        "matchup": {"home": home, "away": away},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "player_data_source": player_pool.get("source"),
        "player_data_retrieved_at_utc": player_pool.get("retrieved_at_utc"),
        "sample_season": player_pool.get("season"),
        "sample_weeks": player_pool.get("last_n_weeks"),
        "trials_per_priced_prop": trials,
        "eligible_players": len(reports),
        "blocked_players": blocked,
        "players": reports,
        "warnings": [
            "Only players explicitly confirmed active starters in the fresh game-day confirmation file are projected.",
            "The confirmation file must be sourced from official NFL/team game-day inactive and starter information.",
            "Recent per-game production is opponent-adjusted with a capped, shrunk defense factor; this adjustment is provisional.",
            "A prop probability is only produced when a sportsbook line is supplied; vig-free edge and EV require both sides of the price.",
            "Normal-approximation dispersion remains provisional pending historical calibration.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Doug's Elite Game Simulator player-prop pipeline")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--pool", default="player_pool.json")
    parser.add_argument("--lines", help="JSON file mapping TEAM:Player:stat to line")
    parser.add_argument("--trials", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--confirmations", required=True,
                        help="Fresh JSON file with official game-day active/starter confirmations")
    parser.add_argument("--team-stats", default="nfl_team_stats.json",
                        help="Current nflverse team defense JSON for opponent adjustment")
    parser.add_argument("--output", default="matchup-player-report.json")
    args = parser.parse_args()
    pool = load_player_pool(args.pool)
    lines = {}
    if args.lines:
        with open(args.lines, "r", encoding="utf-8") as handle:
            lines = json.load(handle)
    with open(args.confirmations, "r", encoding="utf-8") as handle:
        confirmation_data = json.load(handle)
    confirmations = validate_confirmation_file(confirmation_data)
    with open(args.team_stats, "r", encoding="utf-8") as handle:
        team_records = json.load(handle)
    report = analyze_matchup(
        args.home, args.away, pool, lines, args.trials, args.seed,
        confirmations, team_records,
    )
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"Matchup: {args.away.upper()} at {args.home.upper()}")
    print(f"Players projected: {report['eligible_players']}")
    print(f"Players blocked pending confirmation: {len(report['blocked_players'])}")
    print(f"Trials per priced prop: {args.trials:,}")
    print(f"Report saved: {args.output}")
    for warning in report["warnings"]:
        print("WARNING:", warning)


if __name__ == "__main__":
    main()
