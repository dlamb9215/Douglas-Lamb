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


def analyze_matchup(home, away, player_pool, prop_lines=None,
                    trials=100000, seed=42, confirmations=None):
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
        props = []
        for stat in SUPPORTED_STATS[player["position"]]:
            mean = projection["projected_stats"].get(stat)
            if mean is None:
                continue
            line_key = f"{player['team']}:{player['name']}:{stat}"
            line = prop_lines.get(line_key)
            item = {"stat": stat, "recent_per_game_baseline": mean}
            if line is not None:
                item["simulation"] = simulate_player_prop(
                    projection, stat, float(line),
                    trials=trials, seed=seed + index,
                )
            props.append(item)
        reports.append({
            "player": player["name"],
            "team": player["team"],
            "position": player["position"],
            "games_in_sample": player.get("games"),
            "snap_count_per_game": player.get("offense_snaps_per_game"),
            "snap_percentage": player.get("offense_snap_pct_avg"),
            "props": props,
            "data_note": projection["data_note"],
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
            "Recent per-game production is a baseline, not opponent-adjusted.",
            "A prop probability is only produced when a sportsbook line is supplied.",
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
    report = analyze_matchup(
        args.home, args.away, pool, lines, args.trials, args.seed,
        confirmations,
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
