"""Build conservative player workload inputs from CFBD season statistics.

The result is a season-average starting point, not a confirmed next-game workload.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
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
                        output_path: str | Path, teams: set[str] | None = None,
                        classification: str = "fbs") -> list[dict]:
    player_data_path = Path(player_data_path)
    status_path = player_data_path.with_name("player_data_status.json")
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if not status.get("stats_available"):
            raise ValueError("latest CFBD player stats refresh failed; refusing to project from a preserved old cache")
    payload = json.loads(player_data_path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {})
    cached_classification = metadata.get("classification")
    if cached_classification and str(cached_classification).casefold() != classification.casefold():
        raise ValueError("Player cache classification does not match requested team subdivision; refresh player data.")
    retrieved = metadata.get("retrieved_at", "")
    if not retrieved:
        raise ValueError("Player cache is missing retrieval timestamp")
    retrieved_date = retrieved[:10]
    try:
        age = (date.today() - date.fromisoformat(retrieved_date)).days
    except ValueError as exc:
        raise ValueError("Player cache has an invalid retrieval date") from exc
    if age < 0 or age > 2:
        raise ValueError(f"Player cache is {age} days old; refresh before building projections")
    roster_available = bool(metadata.get("roster_available") and payload.get("rosters"))
    roster_ids = set()
    roster_names = set()
    for roster_player in payload.get("rosters", []):
        roster_team = str(roster_player.get("team", "")).casefold()
        roster_id = str(roster_player.get("id", "")).strip()
        roster_name = _norm(str(roster_player.get("firstName", "")) + " " + str(roster_player.get("lastName", "")))
        if roster_team and roster_id:
            roster_ids.add((roster_team, roster_id))
        if roster_team and roster_name:
            roster_names.add((roster_team, roster_name))
    ranking_file = Path(team_profiles_path).with_name(
        "team_rankings.json" if classification == "fbs" else "team_rankings_fcs.json"
    )
    aliases = {}
    if ranking_file.exists():
        ranking_data = json.loads(ranking_file.read_text(encoding="utf-8"))
        aliases = ranking_data.get("metadata", {}).get("team_aliases", {})
    canonical_teams = ({aliases.get(team.casefold(), team).casefold() for team in teams}
                       if teams else None)
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
        if not player or not team:
            continue
        if roster_available:
            player_id = str(row.get("playerId", "")).strip()
            roster_match = ((team.casefold(), player_id) in roster_ids if player_id and roster_ids
                            else (team.casefold(), _norm(player)) in roster_names)
            if not roster_match:
                continue
        if category == "general" and stat_type in {"gp", "gamesplayed", "games"}:
            try:
                aggregate.setdefault((player, team, position), {})["games_played"] = float(row.get("stat", 0))
            except (TypeError, ValueError):
                pass
            continue
        if category not in ALIASES:
            continue
        if canonical_teams and team.casefold() not in canonical_teams:
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
        team_game_count = team_games.get(team.casefold(), 0)
        games = int(stats.get("games_played") or team_game_count)
        games_basis = "player games played" if stats.get("games_played") else "team games (player GP unavailable)"
        if games < 1 or team_game_count < 1:
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
            "games_sampled": games,
            "games_basis": games_basis,
            "roster_verified": roster_available,
            "roster_source": "CollegeFootballData roster API" if roster_available else "",
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
    parser.add_argument("--classification", choices=("fbs", "fcs"), default="fbs")
    args = parser.parse_args()
    players = build_player_inputs(
        args.player_data, args.team_profiles, args.output,
        set(args.teams) if args.teams else None,
        args.classification,
    )
    print(f"Built {len(players)} player projection inputs from current CFBD season data.")
    print(f"Saved to {args.output}; verify availability and next-game workload separately.")


if __name__ == "__main__":
    main()
