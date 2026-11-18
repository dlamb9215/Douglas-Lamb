"""MLB schedule/lineup-aware 1+ hit report CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mlb.data import fetch_player_stats, fetch_schedule
from mlb.model import project_one_plus_hit, simulate_one_plus_hit, validate_confirmed_lineup
from betting_engine.integrations import evaluate_two_way_market


def build_report(game, lineup, season, trials, seed):
    teams = lineup["teams"]
    player_rows = []
    for batting_side, pitching_side in (("home", "away"), ("away", "home")):
        opposing_pitcher_id = teams[pitching_side]["starting_pitcher_id"]
        pitcher = fetch_player_stats(opposing_pitcher_id, season, "pitching")["stat"]
        pitcher_hits = pitcher.get("hits")
        pitcher_bf = pitcher.get("battersFaced")
        if pitcher_hits is None or pitcher_bf is None or float(pitcher_bf) <= 0:
            raise RuntimeError(f"Missing hits/battersFaced for confirmed pitcher {opposing_pitcher_id}")
        for batter in teams[batting_side]["batters"]:
            stats = fetch_player_stats(batter["player_id"], season, "hitting")["stat"]
            hits, pa = stats.get("hits"), stats.get("plateAppearances")
            if hits is None or pa is None or float(pa) <= 0:
                raise RuntimeError(f"Missing hits/plateAppearances for lineup player {batter['player_id']}")
            projection = project_one_plus_hit(
                batter_hits=float(hits), batter_pa=float(pa),
                pitcher_hits_allowed=float(pitcher_hits),
                pitcher_bf=float(pitcher_bf),
                batting_order=batter["batting_order"],
            )
            mc = simulate_one_plus_hit(
                projection["blended_hit_per_pa"],
                projection["projected_plate_appearances"],
                trials=trials, seed=seed + int(batter["player_id"]),
            )
            p_hit = projection["one_plus_hit_probability"]
            market = evaluate_two_way_market(
                sport="MLB", event=f"{game['away']} at {game['home']}",
                market="player_hits", line=0.5,
                selection_a="Over 0.5 hits", probability_a=p_hit,
                odds_a=batter.get("over_odds"),
                selection_b="Under 0.5 hits", probability_b=1-p_hit,
                odds_b=batter.get("under_odds"),
                sportsbook=batter.get("sportsbook", ""),
                quoted_at=batter.get("quoted_at", ""),
                data_ready=True, availability_confirmed=True,
                calibration_ready=False,
            )
            player_rows.append({
                "team_side": batting_side,
                "player_id": batter["player_id"],
                "player_name": batter.get("name", str(batter["player_id"])),
                "opposing_pitcher_id": opposing_pitcher_id,
                "batting_order": batter["batting_order"],
                **projection,
                "monte_carlo_check": mc,
                "market_evaluation": market,
                "bet_decision": "PASS",
                "bet_blockers": ["market-specific calibration not approved"],
            })
    return {
        "sport": "MLB",
        "gamePk": game["gamePk"],
        "game_date": game["game_date"],
        "matchup": f"{game['away']} at {game['home']}",
        "venue": game.get("venue"),
        "season": season,
        "simulation_trials": trials,
        "seed": seed,
        "lineup_source": lineup["source_url"],
        "lineup_checked_at_utc": lineup["checked_at_utc"],
        "lineup_age_hours": lineup["lineup_age_hours"],
        "data_status": "READY_FOR_BASELINE_PROJECTION",
        "calibration_ready": False,
        "betting_status": "PASS_ALL_MARKETS_UNTIL_CALIBRATED",
        "players": player_rows,
        "limitations": [
            "No batter/pitcher handedness splits yet",
            "No pitch mix, contact quality, park/weather, bullpen or umpire adjustment yet",
            "Plate appearances use batting-order priors",
            "This baseline is not market-calibrated and is not an approved wager",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Doug's Elite MLB 1+ Hit Model")
    parser.add_argument("--date", required=True, help="Game date YYYY-MM-DD")
    parser.add_argument("--game-pk", type=int)
    parser.add_argument("--lineup-file")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--trials", type=int, default=500000)
    parser.add_argument("--seed", type=int, default=20261117)
    parser.add_argument("--output", default="mlb-results.json")
    args = parser.parse_args()
    if args.trials < 1000:
        parser.error("--trials must be at least 1,000")
    schedule = fetch_schedule(args.date)
    if not args.lineup_file:
        result = {
            "sport": "MLB", "date": args.date,
            "retrieved_at_utc": schedule["retrieved_at_utc"],
            "schedule_source": schedule["source"],
            "games": schedule["games"],
            "status": "SCHEDULE_ONLY_NO_CONFIRMED_LINEUPS",
            "message": "No player props generated. Supply a current official lineup snapshot after both lineups and starters are confirmed.",
        }
    else:
        if not args.game_pk:
            parser.error("--game-pk is required when --lineup-file is supplied")
        game = next((g for g in schedule["games"] if int(g["gamePk"]) == args.game_pk), None)
        if not game:
            raise RuntimeError(f"Game {args.game_pk} was not found on MLB schedule date {args.date}")
        with Path(args.lineup_file).open(encoding="utf-8") as handle:
            raw_lineup = json.load(handle)
        lineup = validate_confirmed_lineup(raw_lineup, args.game_pk)
        season = args.season or int(args.date[:4])
        result = build_report(game, lineup, season, args.trials, args.seed)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
