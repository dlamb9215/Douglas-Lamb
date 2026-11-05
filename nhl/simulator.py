"""Doug's Elite NHL Simulator.

Fetches current-season NHL team summary data from the NHL Stats API and runs
reproducible Monte Carlo simulations. Missing source statistics are never
silently replaced with fabricated values.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import urllib.parse
import urllib.request
from datetime import datetime, timezone


API_URL = "https://api.nhle.com/stats/rest/en/team/summary"
TEAM_CODES = {
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NJD",
    "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJS",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
}


def current_season_id(now=None):
    now = now or datetime.now(timezone.utc)
    start = now.year if now.month >= 9 else now.year - 1
    return int(f"{start}{start + 1}")


def fetch_team_stats(season_id=None, opener=urllib.request.urlopen):
    """Download regular-season team summary data from the NHL Stats API."""
    season_id = season_id or current_season_id()
    query = urllib.parse.urlencode({
        "isAggregate": "false",
        "isGame": "false",
        "limit": "100",
        "cayenneExp": f"gameTypeId=2 and seasonId={season_id}",
    })
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "DougsEliteNHL-Simulator/1.0"},
    )
    with opener(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("data", [])
    database = {}
    for row in rows:
        code = (
            row.get("teamAbbrev")
            or row.get("teamAbbreviation")
            or row.get("teamCode")
        )
        if isinstance(code, dict):
            code = code.get("default") or code.get("triCode")
        if not code:
            continue
        code = str(code).upper()
        games = row.get("gamesPlayed")
        gf = row.get("goalsForPerGame")
        ga = row.get("goalsAgainstPerGame")
        if not all(is_number(v) for v in (games, gf, ga)) or games <= 0:
            continue
        database[code] = {
            "name": row.get("teamFullName") or code,
            "games_played": int(games),
            "goals_for_per_game": float(gf),
            "goals_against_per_game": float(ga),
            "shots_for_per_game": optional_number(row.get("shotsForPerGame")),
            "shots_against_per_game": optional_number(row.get("shotsAgainstPerGame")),
            "power_play_pct": optional_number(row.get("powerPlayPct")),
            "penalty_kill_pct": optional_number(row.get("penaltyKillPct")),
            "faceoff_win_pct": optional_number(row.get("faceoffWinPct")),
            "season": season_id,
        }
    if len(database) < 20:
        raise RuntimeError(
            f"NHL Stats API returned only {len(database)} usable teams for "
            f"season {season_id}; refusing to simulate from incomplete data."
        )
    return database


def is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def optional_number(value):
    return float(value) if is_number(value) else None


def validate_matchup(database, home, away):
    home, away = home.upper(), away.upper()
    if home == away:
        raise ValueError("Home and away teams must be different.")
    for code in (home, away):
        if code not in TEAM_CODES:
            raise ValueError(f"Unknown NHL team abbreviation: {code}")
        if code not in database:
            raise ValueError(f"No current-season NHL statistics available for {code}.")
        team = database[code]
        for field in ("goals_for_per_game", "goals_against_per_game"):
            if not is_number(team.get(field)) or team[field] <= 0:
                raise ValueError(f"{code} is missing valid {field} data.")
    return home, away


def adjusted_goal_means(database, home, away):
    """Blend each offense's scoring with the opposing defense's goals allowed."""
    h, a = database[home], database[away]
    home_mean = (h["goals_for_per_game"] + a["goals_against_per_game"]) / 2
    away_mean = (a["goals_for_per_game"] + h["goals_against_per_game"]) / 2

    # Modest special-teams adjustment; unavailable rates contribute no adjustment.
    if h.get("power_play_pct") is not None and a.get("penalty_kill_pct") is not None:
        home_mean *= 1 + max(-0.06, min(0.06, (
            (h["power_play_pct"] - 20.0) + (80.0 - a["penalty_kill_pct"])
        ) / 1000))
    if a.get("power_play_pct") is not None and h.get("penalty_kill_pct") is not None:
        away_mean *= 1 + max(-0.06, min(0.06, (
            (a["power_play_pct"] - 20.0) + (80.0 - h["penalty_kill_pct"])
        ) / 1000))

    # Small home-ice scoring lift, explicitly separated from the source stats.
    home_mean += 0.12
    return max(0.2, home_mean), max(0.2, away_mean)


def poisson_sample(rng, mean):
    """Knuth Poisson sampler; NHL scoring means are comfortably small."""
    limit = math.exp(-mean)
    product = 1.0
    count = 0
    while product > limit:
        count += 1
        product *= rng.random()
    return count - 1


def simulate_matchup(
    database, home, away, trials=100000, total_line=6.0,
    puck_line=1.5, seed=42,
):
    if not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be a positive integer.")
    home, away = validate_matchup(database, home, away)
    home_mean, away_mean = adjusted_goal_means(database, home, away)
    rng = random.Random(seed)

    home_wins = away_wins = ties_regulation = 0
    home_covers = away_covers = total_over = total_under = 0
    total_push = home_first_period = away_first_period = 0
    home_goals_sum = away_goals_sum = 0
    home_ot_wins = away_ot_wins = 0

    for _ in range(trials):
        hg = poisson_sample(rng, home_mean)
        ag = poisson_sample(rng, away_mean)
        h1 = poisson_sample(rng, home_mean / 3)
        a1 = poisson_sample(rng, away_mean / 3)
        home_first_period += h1
        away_first_period += a1

        if hg == ag:
            ties_regulation += 1
            # NHL regular-season overtime/shootout is represented by a
            # separate sudden-death resolution with a slight home-ice edge.
            home_ot_probability = 0.52
            if rng.random() < home_ot_probability:
                hg += 1
                home_ot_wins += 1
            else:
                ag += 1
                away_ot_wins += 1

        if hg > ag:
            home_wins += 1
        else:
            away_wins += 1
        if hg - ag > puck_line:
            home_covers += 1
        if ag - hg > puck_line:
            away_covers += 1
        game_total = hg + ag
        if game_total > total_line:
            total_over += 1
        elif game_total < total_line:
            total_under += 1
        else:
            total_push += 1
        home_goals_sum += hg
        away_goals_sum += ag

    pct = lambda n: round(100 * n / trials, 2)
    return {
        "home": home,
        "away": away,
        "trials": trials,
        "seed": seed,
        "season": database[home]["season"],
        "home_mean": round(home_mean, 3),
        "away_mean": round(away_mean, 3),
        "home_win_pct": pct(home_wins),
        "away_win_pct": pct(away_wins),
        "regulation_tie_pct": pct(ties_regulation),
        "home_ot_wins_pct": pct(home_ot_wins),
        "away_ot_wins_pct": pct(away_ot_wins),
        "home_puck_line_pct": pct(home_covers),
        "away_puck_line_pct": pct(away_covers),
        "over_pct": pct(total_over),
        "under_pct": pct(total_under),
        "total_push_pct": pct(total_push),
        "projected_home_goals": round(home_goals_sum / trials, 2),
        "projected_away_goals": round(away_goals_sum / trials, 2),
        "first_period_home_goals": round(home_first_period / trials, 2),
        "first_period_away_goals": round(away_first_period / trials, 2),
    }


def print_report(database, result, total_line, puck_line):
    home, away = result["home"], result["away"]
    h, a = database[home], database[away]
    print("\nDOUG'S ELITE NHL SIMULATOR")
    print("=========================")
    print(f"{a['name']} at {h['name']} | Season {result['season']}")
    print(f"Data sample: {h['games_played']} home-team games; {a['games_played']} away-team games")
    print("\nTEAM MATCHUP")
    print(f"{h['name']}: GF/G {h['goals_for_per_game']:.2f}, GA/G {h['goals_against_per_game']:.2f}, shots for/against {h['shots_for_per_game']}/{h['shots_against_per_game']}")
    print(f"{a['name']}: GF/G {a['goals_for_per_game']:.2f}, GA/G {a['goals_against_per_game']:.2f}, shots for/against {a['shots_for_per_game']}/{a['shots_against_per_game']}")
    print("\nSPECIAL TEAMS (source percentages)")
    print(f"{home}: PP {h['power_play_pct']}% | PK {h['penalty_kill_pct']}%")
    print(f"{away}: PP {a['power_play_pct']}% | PK {a['penalty_kill_pct']}%")
    print("\nSIMULATION")
    print(f"Trials: {result['trials']:,} | Seed: {result['seed']}")
    print(f"Expected goals: {home} {result['home_mean']:.2f} - {away} {result['away_mean']:.2f}")
    print(f"Moneyline: {home} {result['home_win_pct']:.2f}% | {away} {result['away_win_pct']:.2f}%")
    print(f"Regulation tie: {result['regulation_tie_pct']:.2f}%")
    print(f"Overtime winner share: {home} {result['home_ot_wins_pct']:.2f}% | {away} {result['away_ot_wins_pct']:.2f}%")
    print(f"Puck line +/-{puck_line}: {home} -{puck_line} {result['home_puck_line_pct']:.2f}% | {away} +{puck_line} {result['away_puck_line_pct']:.2f}%")
    print(f"Total {total_line}: Over {result['over_pct']:.2f}% | Under {result['under_pct']:.2f}% | Push {result['total_push_pct']:.2f}%")
    print(f"Projected final score: {home} {result['projected_home_goals']:.2f} - {away} {result['projected_away_goals']:.2f}")
    print(f"First-period goals: {home} {result['first_period_home_goals']:.2f} | {away} {result['first_period_away_goals']:.2f}")
    if min(h["games_played"], a["games_played"]) < 10:
        print("WARNING: Early-season sample is under 10 games; estimates are highly uncertain.")
    elif min(h["games_played"], a["games_played"]) < 20:
        print("WARNING: Early-season sample is under 20 games; use extra caution.")
    print("MODEL LIMITATIONS: Team-level Poisson model; goalie-specific starts, line combinations, injuries, travel/rest, and player props are not yet modeled.")
    print("Probabilities are model estimates, not guarantees or proof of a betting edge.")


def main():
    parser = argparse.ArgumentParser(description="Doug's Elite NHL Simulator")
    parser.add_argument("--home", required=True, help="Home team abbreviation")
    parser.add_argument("--away", required=True, help="Away team abbreviation")
    parser.add_argument("--trials", type=int, default=100000)
    parser.add_argument("--total", type=float, default=6.0, help="Sportsbook total-goals line")
    parser.add_argument("--puck-line", type=float, default=1.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--output", default="nhl-simulation-results.txt")
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be greater than zero")
    database = fetch_team_stats(args.season)
    result = simulate_matchup(
        database, args.home, args.away, args.trials,
        args.total, args.puck_line, args.seed,
    )
    lines = []
    import io
    from contextlib import redirect_stdout
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        print_report(database, result, args.total, args.puck_line)
    report = buffer.getvalue()
    print(report, end="")
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(report)
        handle.write("\n\nMACHINE-READABLE RESULTS\n")
        handle.write(json.dumps(result, indent=2))
        handle.write("\n")


if __name__ == "__main__":
    main()
