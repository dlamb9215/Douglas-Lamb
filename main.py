"""
DOUG'S ELITE GAME SIMULATOR
NFL 100,000 Trial Simulation Engine
"""

import random
import argparse
from nfl_data import load_team_stats, get_team_stats


def simulate_game(
    home_mean,
    away_mean,
    home_sd,
    away_sd,
    spread,
    total,
    trials=100000
):
    random.seed(42)

    home_wins = 0
    away_wins = 0
    home_covers = 0
    away_covers = 0
    overs = 0
    unders = 0

    home_scores = []
    away_scores = []

    for _ in range(trials):
        home = max(0, round(random.gauss(home_mean, home_sd)))
        away = max(0, round(random.gauss(away_mean, away_sd)))

        margin = home - away
        game_total = home + away

        home_scores.append(home)
        away_scores.append(away)

        if margin > 0:
            home_wins += 1
        elif margin < 0:
            away_wins += 1

        if margin + spread > 0:
            home_covers += 1
        elif margin + spread < 0:
            away_covers += 1

        if game_total > total:
            overs += 1
        elif game_total < total:
            unders += 1

    return {
        "home_win": home_wins / trials * 100,
        "away_win": away_wins / trials * 100,
        "home_cover": home_covers / trials * 100,
        "away_cover": away_covers / trials * 100,
        "over": overs / trials * 100,
        "under": unders / trials * 100,
        "home_avg": sum(home_scores) / trials,
        "away_avg": sum(away_scores) / trials
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--home", default="HOME")
    parser.add_argument("--away", default="AWAY")
    parser.add_argument("--home-mean", type=float, default=24)
    parser.add_argument("--away-mean", type=float, default=21)
    parser.add_argument("--home-sd", type=float, default=10)
    parser.add_argument("--away-sd", type=float, default=10)
    parser.add_argument("--spread", type=float, default=-3)
    parser.add_argument("--total", type=float, default=45)
    parser.add_argument("--trials", type=int, default=100000)

    args = parser.parse_args()

    database = load_team_stats()

    home = get_team_stats(database, args.home.upper())
    away = get_team_stats(database, args.away.upper())

    print("\nDOUG'S ELITE GAME SIMULATOR")
    print("===========================")
    print(f"{away['name']} AT {home['name']}")

    print("\nTEAM DATABASE CHECK")
    print("Both teams found in database.")

    result = simulate_game(
        args.home_mean,
        args.away_mean,
        args.home_sd,
        args.away_sd,
        args.spread,
        args.total,
        args.trials
    )

    print(f"\nTRIALS: {args.trials:,}")
    print("\nWIN PROBABILITIES")
    print(f"{home['name']}: {result['home_win']:.2f}%")
    print(f"{away['name']}: {result['away_win']:.2f}%")

    print("\nSPREAD PROBABILITIES")
    print(f"{home['name']}: {result['home_cover']:.2f}%")
    print(f"{away['name']}: {result['away_cover']:.2f}%")

    print("\nTOTAL PROBABILITIES")
    print(f"OVER: {result['over']:.2f}%")
    print(f"UNDER: {result['under']:.2f}%")

    print("\nPROJECTED SCORE")
    print(f"{home['name']}: {result['home_avg']:.1f}")
    print(f"{away['name']}: {result['away_avg']:.1f}")

    print("\nWARNING: Scoring averages are placeholders, not matchup projections.")


if __name__ == "__main__":
    main()