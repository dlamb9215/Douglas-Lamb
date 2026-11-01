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
    project_matchup_yardage,
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
    yardage = project_matchup_yardage(
        database, home_code, away_code
    )

    print("\nAUTOMATIC YARDAGE PROJECTIONS")
    print("=============================")

    for team, projection in yardage.items():
        print(f"\n{team}")
        print(f"Passing yards: {projection['passing_yards']}")
        print(f"Rushing yards: {projection['rushing_yards']}")
        print(f"Total yards: {projection['total_yards']}")

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

    home_scoring = home.get("points_for_per_game")
    home_allowed = home.get("points_allowed_per_game")
    away_scoring = away.get("points_for_per_game")
    away_allowed = away.get("points_allowed_per_game")

    if None in (home_scoring, home_allowed, away_scoring, away_allowed):
        print("SIMULATION BLOCKED: Missing scoring data.")
        return

    home_mean = args.home_mean if args.home_mean is not None else (
        home_scoring + away_allowed) / 2

    away_mean = args.away_mean if args.away_mean is not None else (
        away_scoring + home_allowed) / 2

    model_spread = away_mean - home_mean
    model_total = home_mean + away_mean

    spread_line = args.spread if args.spread is not None else model_spread
    print("\nMODEL VS SPORTSBOOK")
    print("====================")

    print(f"Model projected spread: {model_spread:.1f}")
    print(f"Model projected total: {model_total:.1f}")

    if args.spread is not None:
        print(f"Sportsbook spread: {args.spread:+.1f}")
        print(f"Spread difference: {model_spread - args.spread:+.1f}")

        if abs(model_spread - args.spread) >= 3:
            print("Spread edge: MODEL LEAN")
        else:
            print("Spread edge: NO CLEAR EDGE")
    else:
        print("Sportsbook spread: Not provided")

    if args.total is not None:
        print(f"Sportsbook total: {args.total:.1f}")
        print(f"Total difference: {model_total - args.total:+.1f}")
        if abs(model_total - args.total) >= 3:
            print("Total edge: MODEL LEAN")
        else:
            print("Total edge: NO CLEAR EDGE")
    else:
        print("Sportsbook total: Not provided")
    total_line = args.total if args.total is not None else model_total
        

    result = simulate_game(
        home_mean,
        away_mean,
        args.home_sd,
        args.away_sd,
        spread_line,
        total_line,
        args.trials,
    )
    first_half = simulate_game(
        home_mean / 2,
        away_mean / 2,
        args.home_sd / (2 ** 0.5),
        args.away_sd / (2 ** 0.5),
        spread_line / 2,
        total_line / 2,
        args.trials,
    )

    print("\nFIRST-HALF SIMULATION")
    print("=====================")
    print(f"Home win: {first_half['home_win']:.2f}%")
    print(f"Away win: {first_half['away_win']:.2f}%")
    print(f"Home cover: {first_half['home_cover']:.2f}%")
    print(f"Away cover: {first_half['away_cover']:.2f}%")
    print(f"Over: {first_half['over']:.2f}%")
    print(f"Under: {first_half['under']:.2f}%")
    print(f"Projected home points: {first_half['home_avg']:.1f}")
    print(f"Projected away points: {first_half['away_avg']:.1f}")
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

    print("\nPROBABILITY-BASED MODEL LEANS")
    print("=============================")

    if result["home_win"] >= 55:
        print(f"MONEYLINE LEAN: {home['name']} ({result['home_win']:.1f}%)")
    elif result["away_win"] >= 55:
        print(f"MONEYLINE LEAN: {away['name']} ({result['away_win']:.1f}%)")
    else:
        print("MONEYLINE: PASS")

    if result["home_cover"] >= 55:
        print(f"SPREAD LEAN: {home['name']} ({result['home_cover']:.1f}%)")
    elif result["away_cover"] >= 55:
        print(f"SPREAD LEAN: {away['name']} ({result['away_cover']:.1f}%)")
    else:
        print("SPREAD: PASS")

    if result["over"] >= 55:
        print(f"TOTAL LEAN: OVER ({result['over']:.1f}%)")
    elif result["under"] >= 55:
        print(f"TOTAL LEAN: UNDER ({result['under']:.1f}%)")
    else:
        print("TOTAL: PASS")

    print("\nPROJECTED SCORE")
    print(f"{home['name']}: {result['home_avg']:.1f}")
    print(f"{away['name']}: {result['away_avg']:.1f}")


if __name__ == "__main__":
    main()