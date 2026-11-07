"""CLI entry point for Doug's Elite NCAA Football Simulator."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .data import get_profile, load_profiles
from .engine import MarketLines, simulate_game


def main() -> None:
    parser = argparse.ArgumentParser(description="Doug's Elite NCAA Football Simulator")
    parser.add_argument("--home", required=True, help="Home school name")
    parser.add_argument("--away", required=True, help="Away school name")
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--season", default="2026")
    parser.add_argument("--data", default="ncaa/data/team_profiles.csv")
    parser.add_argument("--home-spread", type=float, default=None,
                        help="Sportsbook handicap attached to home team (e.g. -6.5)")
    parser.add_argument("--total", type=float, default=None)
    parser.add_argument("--neutral-site", action="store_true")
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument("--rankings", default="ncaa/data/team_rankings.json")
    parser.add_argument("--output", default="ncaa-results.json")
    args = parser.parse_args()

    profiles = load_profiles(args.data)
    home = get_profile(args.home, profiles)
    away = get_profile(args.away, profiles)
    result = simulate_game(
        home, away, args.trials,
        MarketLines(args.home_spread, args.total),
        args.seed, args.neutral_site,
    )
    result["season"] = args.season
    result["data_file"] = args.data
    ranking_path = Path(args.rankings)
    if ranking_path.exists():
        ranking_data = json.loads(ranking_path.read_text(encoding="utf-8"))
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
    print(f"DOUG'S ELITE NCAA FOOTBALL SIMULATOR | {args.season}")
    print(f"{args.away} at {args.home}")
    print(f"Trials: {args.trials:,} | Seed: {args.seed}")
    print(f"Projected score: {args.home} {result['projected_score'][args.home]} - "
          f"{args.away} {result['projected_score'][args.away]}")
    print(f"Home win: {result['home_win_probability']:.1%} | "
          f"Away win: {result['away_win_probability']:.1%}")
    print(f"Projected total: {result['projected_total']:.1f}")
    h1 = result["projected_first_half_score"]
    print(f"Projected first half: {args.home} {h1[args.home]:.1f} - {args.away} {h1[args.away]:.1f}")
    print(f"First-half home lead probability: {result['first_half_win_probability_home']:.1%}")
    print("Projected score ranges (10th percentile / median / 90th percentile):")
    for team, band in result["score_ranges"].items():
        print(f"  {team}: {band['p10']} / {band['median']} / {band['p90']}")
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
