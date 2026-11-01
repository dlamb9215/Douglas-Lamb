"""
DOUG'S ELITE GAME SIMULATOR
Statistics-Based NFL Simulation Foundation
"""

import argparse
from nfl_data import load_team_stats, get_team_stats


def simulate_game(home, away, trials=100000):
    import random

    random.seed(42)

    home_wins = 0
    away_wins = 0
    ties = 0

    for _ in range(trials):
        home_score = max(0, round(random.gauss(24, 10)))
        away_score = max(0, round(random.gauss(21, 10)))

        if home_score > away_score:
            home_wins += 1
        elif away_score > home_score:
            away_wins += 1
        else:
            ties += 1

    return {
        "home_win": home_wins / trials * 100,
        "away_win": away_wins / trials * 100,
        "ties": ties / trials * 100
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--trials", type=int, default=100000)

    args = parser.parse_args()

    database = load_team_stats()

    home = get_team_stats(database, args.home.upper())
    away = get_team_stats(database, args.away.upper())

    print("\nDOUG'S ELITE GAME SIMULATOR")
    print("===========================")
    print(f"{away['name']} AT {home['name']}")

    print("\nTEAM DATABASE CHECK")
    print("Home team:", home["name"])
    print("Away team:", away["name"])
    print("Both teams found in database.")

    print("\nSTATISTICS STATUS")
    print("Team structures loaded.")
    print("Verified statistics must be added before projections.")

    print("\nSIMULATION")
    print("The current scoring model still uses placeholder averages.")
    print("It is not yet a matchup-based prediction.")

    result = simulate_game(home, away, args.trials)

    print(f"\nTRIALS: {args.trials:,}")
    print(f"{home['name']} win probability: {result['home_win']:.2f}%")
    print(f"{away['name']} win probability: {result['away_win']:.2f}%")
    print(f"Tie probability: {result['ties']:.2f}%")


if __name__ == "__main__":
    main()