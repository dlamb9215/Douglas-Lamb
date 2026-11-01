"""
DOUG'S ELITE GAME SIMULATOR
NFL MATCHUP AND 100,000 TRIAL ENGINE
"""

import random
import argparse

from nfl_data import (
    load_team_stats,
    get_team_stats,
    compare_team_stats,
    check_matchup_data,
)


def simulate_game(
    home_mean,
    away_mean,
    home_sd,
    away_sd,
    spread,
    total,
    trials=100000
):
    """Run a reproducible scoring simulation."""

    if trials < 1:
        raise ValueError("Trials must be greater than zero.")

    if home_sd < 0 or away_sd < 0:
        raise ValueError("Standard deviations cannot be negative.")

    rng = random.Random(42)

    home_wins = 0
    away_wins = 0
    ties = 0

    home_covers = 0
    away_covers = 0
    spread_pushes = 0

    overs = 0
    unders = 0
    total_pushes = 0

    home_score_sum = 0
    away_score_sum = 0

    for _ in range(trials):

        home = max(0, round(rng.gauss(home_mean, home_sd)))
        away = max(0, round(rng.gauss(away_mean, away_sd)))

        margin = home - away
        game_total = home + away

        home_score_sum += home
        away_score_sum += away

        if margin > 0:
            home_wins += 1
        elif margin < 0:
            away_wins += 1
        else:
            ties += 1

        spread_result = margin + spread

        if spread_result > 0:
            home_covers += 1
        elif spread_result < 0:
            away_covers += 1
        else:
            spread_pushes += 1

        if game_total > total:
            overs += 1
        elif game_total < total:
            unders += 1
        else:
            total_pushes += 1

    return {
        "home_win": home_wins / trials * 100,
        "away_win": away_wins / trials * 100,
        "tie": ties / trials * 100,
        "home_cover": home_covers / trials * 100,
        "away_cover": away_covers / trials * 100,
        "spread_push": spread_pushes / trials * 100,
        "over": overs / trials * 100,
        "under": unders / trials * 100,
        "total_push": total_pushes / trials * 100,
        "home_avg": home_score_sum / trials,
        "away_avg": away_score_sum / trials,
    }


def print_matchup_report(database, home_code, away_code):
    """Print both teams' offense and opposing defense."""

    report = compare_team_stats(database, home_code, away_code)

    home = get_team_stats(database, home_code)
    away = get_team_stats(database, away_code)

    print("\nTEAM VS TEAM BREAKDOWN")
    print("======================")

    print(f"\n{home['name']} OFFENSE vs {away['name']} DEFENSE")
    print(f"{away['name']} OFFENSE vs {home['name']} DEFENSE")

    for category in ("passing", "rushing", "total"):

        print(f"\n{category.upper()}")

        print(
            f"{home['name']} offense:",
            report[category]["team_a_offense"]
        )

        print(
            f"{away['name']} defense:",
            report[category]["team_b_defense"]
        )

        print(
            f"{away['name']} offense:",
            report[category]["team_b_offense"]
        )

        print(
            f"{home['name']} defense:",
            report[category]["team_a_defense"]
        )

    print("\nTURNOVER COMPARISON")
    print(home["name"], home["turnovers"])
    print(away["name"], away["turnovers"])


def main():

    parser = argparse.ArgumentParser(
        description="Doug's Elite Game Simulator"
    )

    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)

    parser.add_argument("--home-mean", type=float)
    parser.add_argument("--away-mean", type=float)

    parser.add_argument("--home-sd", type=float, default=10)
    parser.add_argument("--away-sd", type=float, default=10)

    parser.add_argument("--spread", type=float)
    parser.add_argument("--total", type=float)

    parser.add_argument("--trials", type=int, default=100000)

    args = parser.parse_args()

    database = load_team_stats()

    home_code = args.home.upper()
    away_code = args.away.upper()

    if home_code == away_code:
        parser.error("Home and away teams must be different.")

    home = get_team_stats(database, home_code)
    away = get_team_stats(database, away_code)

    print("\nDOUG'S ELITE GAME SIMULATOR")
    print("===========================")
    print(f"{away['name']} AT {home['name']}")

    print_matchup_report(database, home_code, away_code)

    data_check = check_matchup_data(
        database, home_code, away_code
    )

    if not data_check["ready"]:

        print("\nSIMULATION BLOCKED")
        print("==================")
        print("Required verified team statistics are missing.")

        for team, missing in data_check["missing"].items():
            print(f"\n{team} missing:")
            for item in missing:
                print("-", item)

        print("\nNo matchup prediction was generated.")
        return

    required_lines = {
        "home scoring average": args.home_mean,
        "away scoring average": args.away_mean,
        "spread": args.spread,
        "game total": args.total,
    }

    missing_lines = [
        name for name, value in required_lines.items()
        if value is None
    ]

    if missing_lines:
        print("\nSIMULATION NOT RUN")
        print("Missing inputs:", ", ".join(missing_lines))
        return

    result = simulate_game(
        args.home_mean,
        args.away_mean,
        args.home_sd,
        args.away_sd,
        args.spread,
        args.total,
        args.trials,
    )

    print(f"\nSIMULATION RESULTS: {args.trials:,} TRIALS")

    print("\nWIN PROBABILITIES")
    print(f"{home['name']}: {result['home_win']:.2f}%")
    print(f"{away['name']}: {result['away_win']:.2f}%")
    print(f"Tie: {result['tie']:.2f}%")

    print("\nSPREAD PROBABILITIES")
    print(f"{home['name']}: {result['home_cover']:.2f}%")
    print(f"{away['name']}: {result['away_cover']:.2f}%")
    print(f"Push: {result['spread_push']:.2f}%")

    print("\nOVER / UNDER")
    print(f"Over: {result['over']:.2f}%")
    print(f"Under: {result['under']:.2f}%")
    print(f"Push: {result['total_push']:.2f}%")

    print("\nPROJECTED SCORE")
    print(f"{home['name']}: {result['home_avg']:.1f}")
    print(f"{away['name']}: {result['away_avg']:.1f}")

    print(
        "\nNOTE: Scoring averages are supplied inputs, "
        "not automatically calculated projections."
    )


if __name__ == "__main__":
    main()