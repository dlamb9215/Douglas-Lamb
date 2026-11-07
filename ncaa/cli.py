"""CLI entry point for Doug's Elite NCAA Football Simulator."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .data import get_profile, load_profiles
from .engine import MarketLines, simulate_game
from .market import remove_vig_two_way, expected_value_per_100
from .scenarios import run_sensitivity_scenarios
from .pregame import load_pregame_checks
from .players import simulate_players
from .forecast_ledger import append_forecast


def main() -> None:
    parser = argparse.ArgumentParser(description="Doug's Elite NCAA Football Simulator")
    parser.add_argument("--home", required=True, help="Home school name")
    parser.add_argument("--away", required=True, help="Away school name")
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--season", default="2026")
    parser.add_argument("--classification", choices=("fbs", "fcs"), default="fbs")
    parser.add_argument("--data", default=None)
    parser.add_argument("--allow-prior", action="store_true", help="Allow league-average priors when a team profile is missing")
    parser.add_argument("--home-spread", type=float, default=None,
                        help="Sportsbook handicap attached to home team (e.g. -6.5)")
    parser.add_argument("--total", type=float, default=None)
    parser.add_argument("--home-ml-odds", type=float, default=None)
    parser.add_argument("--away-ml-odds", type=float, default=None)
    parser.add_argument("--over-odds", type=float, default=None)
    parser.add_argument("--under-odds", type=float, default=None)
    parser.add_argument("--neutral-site", action="store_true")
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument("--rankings", default=None)
    parser.add_argument("--output", default="ncaa-results.json")
    parser.add_argument("--pregame-checks", default=None, help="Sourced pregame verification JSON")
    parser.add_argument("--require-verified-pregame", action="store_true")
    parser.add_argument("--players", default=None, help="Current, sourced player workload JSON")
    parser.add_argument("--kickoff", default=None, help="Game kickoff ISO-8601 timestamp with timezone")
    parser.add_argument("--weather-json", default=None, help="Venue weather context JSON")
    parser.add_argument("--ledger", default=None, help="Optional CSV path for timestamped forecast history")
    args = parser.parse_args()

    data_path = args.data or ("ncaa/data/team_profiles.csv" if args.classification == "fbs" else "ncaa/data/team_profiles_fcs.csv")
    rankings_file = args.rankings or ("ncaa/data/team_rankings.json" if args.classification == "fbs" else "ncaa/data/team_rankings_fcs.json")
    ranking_path = Path(rankings_file)
    ranking_data = json.loads(ranking_path.read_text(encoding="utf-8")) if ranking_path.exists() else {}
    aliases = ranking_data.get("metadata", {}).get("team_aliases", {})
    args.home = aliases.get(args.home.casefold(), args.home)
    args.away = aliases.get(args.away.casefold(), args.away)
    if args.require_verified_pregame and not args.pregame_checks:
        parser.error("--require-verified-pregame needs --pregame-checks")
    pregame = (load_pregame_checks(
        args.pregame_checks, args.home, args.away,
        require_verified=args.require_verified_pregame,
    ) if args.pregame_checks else {
        "all_verified": False,
        "unverified": ["starting quarterbacks", "injuries", "weather", "sportsbook"],
        "warning": "No sourced pregame checks supplied.",
    })
    profiles = load_profiles(data_path)
    missing_profiles = [name for name in (args.home, args.away) if name.casefold() not in profiles]
    if missing_profiles and not args.allow_prior:
        parser.error("Missing current team profile(s): " + ", ".join(missing_profiles) +
                     ". Refresh the selected classification or explicitly pass --allow-prior.")
    home = get_profile(args.home, profiles)
    away = get_profile(args.away, profiles)
    result = simulate_game(
        home, away, args.trials,
        MarketLines(args.home_spread, args.total),
        args.seed, args.neutral_site,
    )
    result["scenario_sensitivity"] = run_sensitivity_scenarios(
        home, away, args.trials, MarketLines(args.home_spread, args.total),
        args.seed, args.neutral_site,
    )
    result["pregame_verification"] = pregame
    weather_context = None
    if args.weather_json:
        weather_context = json.loads(Path(args.weather_json).read_text(encoding="utf-8"))
        result["weather_context"] = weather_context
    if args.players:
        result["player_projections"] = simulate_players(args.players, args.trials, args.seed + 1000)
    result["season"] = args.season
    result["classification"] = args.classification
    result["sportsbook_analysis"] = {}
    if (args.home_ml_odds is None) != (args.away_ml_odds is None):
        parser.error("Provide both moneyline prices.")
    if args.home_ml_odds is not None:
        fair = remove_vig_two_way(args.home_ml_odds, args.away_ml_odds)
        hp = result["home_win_probability"]
        result["sportsbook_analysis"]["moneyline"] = {
            **fair, "model_home_probability": hp,
            "model_edge_home": round(hp - fair["fair_probability_a"], 4),
            "home_ev_per_100": expected_value_per_100(hp, args.home_ml_odds),
            "away_ev_per_100": expected_value_per_100(result["away_win_probability"], args.away_ml_odds)
        }
    if (args.over_odds is None) != (args.under_odds is None):
        parser.error("Provide both over and under prices.")
    if args.over_odds is not None:
        if args.total is None or "over_probability" not in result["market"]:
            parser.error("A --total line is required with over/under prices.")
        fair = remove_vig_two_way(args.over_odds, args.under_odds)
        op = result["market"]["over_probability"]
        result["sportsbook_analysis"]["total"] = {
            **fair, "model_over_probability": op,
            "model_edge_over": round(op - fair["fair_probability_a"], 4),
            "over_ev_per_100": expected_value_per_100(op, args.over_odds),
            "under_ev_per_100": expected_value_per_100(result["market"]["under_probability"], args.under_odds)
        }
    result["market_prices"] = {
        "home_moneyline": args.home_ml_odds,
        "away_moneyline": args.away_ml_odds,
        "over": args.over_odds,
        "under": args.under_odds,
    }
    if args.ledger:
        ledger_kickoff = args.kickoff or (weather_context or {}).get("kickoff")
        result["forecast_ledger"] = append_forecast(
            result, args.ledger, kickoff=ledger_kickoff,
        )
    result["data_file"] = data_path
    if ranking_data:
        ranking_teams = ranking_data.get("teams", {})
        def team_rank(name):
            key = next((k for k in ranking_teams if k.casefold() == name.casefold()), None)
            return ranking_teams.get(key, {}) if key else {}
        result["national_rank_context"] = {
            args.home: team_rank(args.home),
            args.away: team_rank(args.away),
            "metadata": ranking_data.get("metadata", {}),
        }
    else:
        result["national_rank_context"] = {"warning": "National ranking file unavailable."}
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"DOUG'S ELITE NCAA FOOTBALL SIMULATOR | {args.season} | {args.classification.upper()}")
    print(f"{args.away} at {args.home}")
    print(f"Trials: {args.trials:,} | Seed: {args.seed}")
    print(f"Projected score: {args.home} {result['projected_score'][args.home]} - "
          f"{args.away} {result['projected_score'][args.away]}")
    print(f"Home win: {result['home_win_probability']:.1%} | "
          f"Away win: {result['away_win_probability']:.1%}")
    print(f"Projected total: {result['projected_total']:.1f}")
    h1 = result["projected_first_half_score"]
    print(f"Projected first half: {args.home} {h1[args.home]:.1f} - {args.away} {h1[args.away]:.1f}")
    print(f"First-half home lead: {result['first_half_win_probability_home']:.1%} | "
          f"Away lead: {result['first_half_win_probability_away']:.1%} | "
          f"Tie: {result['first_half_tie_probability']:.1%}")
    print("Projected score ranges (10th percentile / median / 90th percentile):")
    for team, band in result["score_ranges"].items():
        print(f"  {team}: {band['p10']} / {band['median']} / {band['p90']}")
    print("Sensitivity scenarios (assumption stress tests, not calibrated probabilities):")
    for scenario, values in result["scenario_sensitivity"]["scenarios"].items():
        score = values["projected_score"]
        print(f"  {scenario}: {args.home} {score[args.home]} - {args.away} {score[args.away]} | "
              f"home win {values['home_win_probability']:.1%} | total {values['projected_total']:.1f}")
    if args.players:
        print("PLAYER PROJECTIONS (manual sourced workload inputs):")
        for player in result["player_projections"]:
            print(f"  {player['player']} ({player['team']}): {player['projected_yards']} yards, "
                  f"{player['expected_successes']} successes, "
                  f"{player['expected_touchdowns']} TDs")
    if result["sportsbook_analysis"]:
        print("Vig-adjusted sportsbook comparison:")
        print(json.dumps(result["sportsbook_analysis"], indent=2))
    if result["market"]:
        print("Market probabilities:")
        for key, value in result["market"].items():
            if key.endswith("probability"):
                print(f"  {key}: {value:.1%}")
            else:
                print(f"  {key}: {value}")
    if result["data_quality"]["warnings"]:
        print("DATA WARNINGS:")
        for warning in result["data_quality"]["warnings"]:
            print(f"  - {warning}")
    print(f"Full results saved to {args.output}")


if __name__ == "__main__":
    main()
