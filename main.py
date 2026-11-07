"""
DOUG'S ELITE GAME SIMULATOR
NFL MATCHUP AND 100,000 TRIAL ENGINE
"""

import random
import argparse
import json
from drive_simulator import simulate_drive_game
from nfl_data import (
    load_team_stats,
    get_team_stats,
    compare_team_stats,
    check_matchup_data,
    project_matchup_yardage,
    project_matchup_scoring,
)



def simulate_game(
    home_mean,
    away_mean,
    home_sd,
    away_sd,
    spread,
    total,
    trials=100000,
    first_half=False,
    seed=42,
    home_turnover_rate=0.10,
    away_turnover_rate=0.10,
):
    """Run the drive-based scoring simulation."""

    return simulate_drive_game(
        home_mean=home_mean,
        away_mean=away_mean,
        spread=spread,
        total=total,
        trials=trials,
        seed=seed,
        first_half=first_half,
        home_sd=home_sd,
        away_sd=away_sd,
        home_turnover_rate=home_turnover_rate,
        away_turnover_rate=away_turnover_rate,
    )





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
    parser.add_argument("--home-odds", type=int)
    parser.add_argument("--away-odds", type=int)
    parser.add_argument("--over-odds", type=int)
    parser.add_argument("--under-odds", type=int)
    parser.add_argument("--trials", type=int, default=100000)
    parser.add_argument("--pregame-report", help="Fresh pregame context JSON")
    parser.add_argument(
        "--neutral-site",
        action="store_true",
        help="Disable the 1.5-point home-field scoring adjustment for neutral venues",
    )
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible simulations")

    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be greater than zero")
    def implied_probability(odds):
        if odds is None:
            return None
        if odds > 0:
            return 100 * 100 / (odds + 100)
        if odds < 0:
            return 100 * abs(odds) / (abs(odds) + 100)
        raise ValueError("Odds cannot be zero.")

    print("\nSPORTSBOOK IMPLIED PROBABILITIES")
    print("================================")
    if args.home_odds is not None and args.away_odds is not None:
        home_raw = implied_probability(args.home_odds)
        away_raw = implied_probability(args.away_odds)
        market_total = home_raw + away_raw

        print("\nVIG-FREE MONEYLINE PROBABILITIES")
        print(f"Home: {home_raw / market_total * 100:.2f}%")
        print(f"Away: {away_raw / market_total * 100:.2f}%")

    if args.over_odds is not None and args.under_odds is not None:
        over_raw = implied_probability(args.over_odds)
        under_raw = implied_probability(args.under_odds)
        market_total = over_raw + under_raw

        print("\nVIG-FREE TOTAL PROBABILITIES")
        print(f"Over: {over_raw / market_total * 100:.2f}%")
        print(f"Under: {under_raw / market_total * 100:.2f}%")
    for label, odds in [
        ("Home ML", args.home_odds),
        ("Away ML", args.away_odds),
        ("Over", args.over_odds),
        ("Under", args.under_odds),
    ]:
        probability = implied_probability(odds)
        if probability is not None:
            print(f"{label}: {probability:.2f}%")
    database = load_team_stats()

    timestamps = sorted({
        team.get("data_updated_at")
        for team in database.values()
        if team.get("data_updated_at")
    })
    seasons = sorted({
        team.get("season")
        for team in database.values()
        if team.get("season") is not None
    })
    print("\nDATA FRESHNESS")
    print("==============")
    print(f"Season: {seasons[-1] if seasons else 'Not recorded'}")
    print(f"Data refreshed: {timestamps[-1] if timestamps else 'Timestamp unavailable'}")
    print(f"Teams loaded: {len(database)}")

    home_code = args.home.upper()
    away_code = args.away.upper()

    if home_code == away_code:
        parser.error("Home and away teams must be different.")

    pregame_report = None
    if args.pregame_report:
        try:
            with open(args.pregame_report, encoding="utf-8") as handle:
                pregame_report = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"Could not read pregame report: {exc}")
        if pregame_report.get("home") != home_code or pregame_report.get("away") != away_code:
            parser.error("Pregame report teams do not match requested matchup.")

    home = get_team_stats(database, home_code)
    away = get_team_stats(database, away_code)

    print("\nDOUG'S ELITE GAME SIMULATOR")
    print("===========================")
    print(f"{away['name']} AT {home['name']}")

    print_matchup_report(database, home_code, away_code)

    if pregame_report:
        print("\nLIVE PREGAME PLAYER CONTEXT")
        print("===========================")
        print(f"Source: {pregame_report.get('source')}")
        print(f"Retrieved: {pregame_report.get('retrieved_at_utc')}")
        for team_code in (home_code, away_code):
            details = pregame_report["teams"][team_code]
            print(f"\n{team_code} quarterback depth chart (not confirmed starters):")
            for qb in details.get("quarterback_depth_chart", []):
                print(f"  #{qb.get('depth_order')} {qb.get('name')} | roster: {qb.get('roster_status')} | injury: {qb.get('injury_status')}")
            print(f"Reported injuries: {details.get('reported_injuries', [])}")
        print("Final game-day inactives and starting QBs: NOT CONFIRMED")
        print("Player props: BLOCKED")
        print("Team scoring injury adjustment: NOT MODELED")
    else:
        print("\\nPREGAME PLAYER CONTEXT: NOT PROVIDED")

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
    if pregame_report and not pregame_report.get("team_simulation_ready", False):
        print("\nSIMULATION BLOCKED")
        print("==================")
        print("Latest pregame data does not show an available QB1 for both teams.")
        for blocker in pregame_report.get("team_simulation_blockers", []):
            print("-", blocker)
        print("No win, spread or total probabilities were generated.")
        return

    print("\nDATA QUALITY CHECK")
    print("==================")
    print("Required matchup statistics: VERIFIED")
    print("Team scoring data: CHECKED")
    print("Turnover rates: INCLUDED IN DRIVE SIMULATION")
    print("Overtime: SIMPLIFIED TWO-POSSESSION APPROXIMATION")
    print("Current weekly injury/depth context: LOADED")
    print("BETTING READINESS: NOT READY")
    if pregame_report:
        for blocker in pregame_report.get("betting_readiness_blockers", []):
            print("-", blocker)
    print("Final inactives and official starting lineups: NOT CONFIRMED")

    print("\nMODEL CONFIDENCE WARNING")
    print("========================")
    print("55% lean threshold is preliminary, not historically calibrated.")
    print("First-half projections use estimated scoring splits.")
    print("Do not treat a model lean as a guaranteed betting edge.")
    home_scoring = home.get("points_for_per_game")
    home_allowed = home.get("points_allowed_per_game")
    away_scoring = away.get("points_for_per_game")
    away_allowed = away.get("points_allowed_per_game")

    if None in (home_scoring, home_allowed, away_scoring, away_allowed):
        print("SIMULATION BLOCKED: Missing scoring data.")
        return

    home_field_points = 0 if args.neutral_site else 1.5
    scoring_projection = project_matchup_scoring(
        database, home_code, away_code, home_field_points=home_field_points
    )

    home_mean = (
        args.home_mean if args.home_mean is not None
        else scoring_projection[home_code]
    )
    away_mean = (
        args.away_mean if args.away_mean is not None
        else scoring_projection[away_code]
    )

    print("\nMATCHUP-ADJUSTED SCORING PROJECTIONS")
    print("===================================")
    print(f"{home['name']}: {home_mean:.2f} points")
    print(f"{away['name']}: {away_mean:.2f} points")
    if args.neutral_site:
        print("Neutral-site mode: no home-field scoring adjustment; shrunk yardage matchup adjustment retained.")
    else:
        print("Includes a 1.5-point home-field adjustment and a shrunk yardage matchup adjustment.")

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
        seed=args.seed,
        home_turnover_rate=home['turnovers']['giveaways'] / max(home.get('games_played', 1), 1) / 10.6,
        away_turnover_rate=away['turnovers']['giveaways'] / max(away.get('games_played', 1), 1) / 10.6,
        )
    print("\nMODEL EDGE VS FAIR MARKET")
    print("=========================")

    if args.home_odds is not None and args.away_odds is not None:
        home_fair = implied_probability(args.home_odds)
        away_fair = implied_probability(args.away_odds)
        fair_total = home_fair + away_fair

        home_fair = home_fair / fair_total * 100
        away_fair = away_fair / fair_total * 100

        print(f"Home ML edge: {result['home_win'] - home_fair:+.2f} percentage points")
        print(f"Away ML edge: {result['away_win'] - away_fair:+.2f} percentage points")

    if args.over_odds is not None and args.under_odds is not None:
        over_fair = implied_probability(args.over_odds)
        under_fair = implied_probability(args.under_odds)
        fair_total = over_fair + under_fair

        over_fair = over_fair / fair_total * 100
        under_fair = under_fair / fair_total * 100

        print(f"Over edge: {result['over'] - over_fair:+.2f} percentage points")
        print(f"Under edge: {result['under'] - under_fair:+.2f} percentage points")
    

    first_half = simulate_game(
        home_mean,
        away_mean,
        args.home_sd,
        args.away_sd,
        spread_line / 2,
        total_line / 2,
        args.trials,
        first_half=True,
        seed=args.seed + 1,
        home_turnover_rate=home['turnovers']['giveaways'] / max(home.get('games_played', 1), 1) / 10.6,
        away_turnover_rate=away['turnovers']['giveaways'] / max(away.get('games_played', 1), 1) / 10.6,
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
    print(f"Random seed: {args.seed} (first-half seed: {args.seed + 1})")

    print("\nWIN PROBABILITIES")
    print(f"{home['name']}: {result['home_win']:.2f}%")
    print(f"{away['name']}: {result['away_win']:.2f}%")
    print(f"Regulation ties sent to overtime: {result['overtime']:.2f}%")
    print(f"Final tie probability: {result['tie']:.2f}%")

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

    if args.home_odds is None or args.away_odds is None:
        print("MONEYLINE: PASS - current two-way sportsbook prices are required.")
    elif result["home_win"] >= 55:
        print(f"MODEL FAVORITE: {home['name']} ({result['home_win']:.1f}%)")
    elif result["away_win"] >= 55:
        print(f"MODEL FAVORITE: {away['name']} ({result['away_win']:.1f}%)")
    else:
        print("MONEYLINE: PASS - no clear model favorite.")

    if args.spread is None:
        print("SPREAD: PASS - current sportsbook spread is required.")
    elif result["home_cover"] >= 55:
        print(f"MODEL SPREAD LEAN: {home['name']} ({result['home_cover']:.1f}%)")
    elif result["away_cover"] >= 55:
        print(f"MODEL SPREAD LEAN: {away['name']} ({result['away_cover']:.1f}%)")
    else:
        print("SPREAD: PASS - no clear model lean.")

    if args.total is None:
        print("TOTAL: PASS - current sportsbook total is required.")
    elif result["over"] >= 55:
        print(f"MODEL TOTAL LEAN: OVER ({result['over']:.1f}%)")
    elif result["under"] >= 55:
        print(f"MODEL TOTAL LEAN: UNDER ({result['under']:.1f}%)")
    else:
        print("TOTAL: PASS - no clear model lean.")

    if not pregame_report or not pregame_report.get("betting_ready", False):
        print("FINAL BETTING STATUS: PASS - one or more pregame readiness gates remain open.")
        if pregame_report:
            for blocker in pregame_report.get("betting_readiness_blockers", []):
                print(f"READINESS BLOCKER: {blocker}")

    print("\nPROJECTED SCORE")
    print(f"{home['name']}: {result['home_avg']:.1f}")
    print(f"{away['name']}: {result['away_avg']:.1f}")


if __name__ == "__main__":
    main()