"""Build conservative player workload inputs from CFBD season statistics.

The result is a season-average starting point, not a confirmed next-game workload.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def _norm(value: str) -> str:
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


ALIASES = {
    "passing": {
        "attempts": {"att", "attempts", "passingattempts", "passattempts"},
        "completions": {"cmp", "completions", "passingcompletions", "passcompletions"},
        "yards": {"yds", "yards", "passingyards", "passyards"},
        "touchdowns": {"td", "touchdowns", "passingtd", "passingtouchdowns"},
    },
    "rushing": {
        "attempts": {"car", "att", "attempts", "rushingattempts", "rushattempts"},
        "yards": {"yds", "yards", "rushingyards", "rushyards"},
        "touchdowns": {"td", "touchdowns", "rushingtd", "rushingtouchdowns"},
    },
    "receiving": {
        "receptions": {"rec", "receptions", "catches"},
        "yards": {"yds", "yards", "receivingyards", "recievingyards"},
        "touchdowns": {"td", "touchdowns", "receivingtd", "receivingtouchdowns"},
    },
}


def build_player_inputs(player_data_path: str | Path, team_profiles_path: str | Path,
                        output_path: str | Path, teams: set[str] | None = None) -> list[dict]:
    payload = json.loads(Path(player_data_path).read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {})
    retrieved = metadata.get("retrieved_at", "")
    if not retrieved:
        raise ValueError("Player cache is missing retrieval timestamp")
    retrieved_date = retrieved[:10]
    team_games = {}
    with Path(team_profiles_path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            team = row.get("team", "").strip()
            games = int(float(row.get("games_sampled", 0) or 0))
            if team and games > 0:
                team_games[team.casefold()] = games

    aggregate = {}
    for row in payload.get("season_stats", []):
        player = str(row.get("player", "")).strip()
        team = str(row.get("team", "")).strip()
        position = str(row.get("position", "")).strip().upper()
        category = _norm(row.get("category", ""))
        stat_type = _norm(row.get("statType", ""))
        if not player or not team or category not in ALIASES:
            continue
        if teams and team.casefold() not in {t.casefold() for t in teams}:
            continue
        stat_name = next((name for name, aliases in ALIASES[category].items()
                          if stat_type in aliases), None)
        if stat_name is None:
            continue
        try:
            value = float(str(row.get("stat", "")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if value < 0:
            continue
        key = (player, team, position)
        aggregate.setdefault(key, {}).setdefault(category, {})[stat_name] = value

    result = []
    for (player, team, position), stats in sorted(aggregate.items()):
        games = team_games.get(team.casefold(), 0)
        if games < 1:
            continue
        if position in {"QB"}:
            role, group = "QB", stats.get("passing", {})
            opportunities = group.get("attempts", 0.0)
            successes = group.get("completions", 0.0)
        elif position in {"RB", "HB", "FB"}:
            role, group = "RB", stats.get("rushing", {})
            opportunities = group.get("attempts", 0.0)
            successes = opportunities
        elif position in {"WR"}:
            role, group = "WR", stats.get("receiving", {})
            opportunities = group.get("receptions", 0.0)
            successes = opportunities
        elif position in {"TE"}:
            role, group = "TE", stats.get("receiving", {})
            opportunities = group.get("receptions", 0.0)
            successes = opportunities
        else:
            continue
        if opportunities <= 0 or successes <= 0:
            continue
        total_yards = group.get("yards", 0.0)
        if total_yards <= 0:
            continue
        total_tds = group.get("touchdowns", 0.0)
        per_success = total_yards / successes
        result.append({
            "player": player,
            "team": team,
            "role": role,
            "expected_opportunities": round(opportunities / games, 3),
            "success_probability": round(successes / opportunities, 5),
            "yards_per_success": round(per_success, 3),
            "yards_sd_per_success": round(max(2.0, per_success * 0.60), 3),
            "touchdown_rate_per_opportunity": round(total_tds / opportunities, 5),
            "source": "CollegeFootballData player season stats",
            "as_of": retrieved_date,
            "prop_lines": {},
        })
    if not result:
        raise ValueError("No usable QB/RB/WR/TE player season rows found; refusing to write empty inputs")
    Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build NCAA player projection inputs from CFBD cache")
    parser.add_argument("--player-data", default="ncaa/data/player_season_data.json")
    parser.add_argument("--team-profiles", default="ncaa/data/team_profiles.csv")
    parser.add_argument("--output", default="ncaa/data/player_projection_inputs.json")
    parser.add_argument("--teams", nargs="*", default=None)
    args = parser.parse_args()
    players = build_player_inputs(
        args.player_data, args.team_profiles, args.output,
        set(args.teams) if args.teams else None,
    )
    print(f"Built {len(players)} player projection inputs from current CFBD season data.")
    print(f"Saved to {args.output}; verify availability and next-game workload separately.")


if __name__ == "__main__":
    main()
