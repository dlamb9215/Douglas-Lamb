"""Experimental NBA player prop projections from ESPN game logs.

This module uses roster membership and recent player game logs. It excludes players
listed Out, Doubtful or Questionable in the official NBA report. It does NOT confirm
starters or predict role changes; projected minutes are statistical baselines only.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from nba.injuries import fetch_official_injuries

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
ALIASES = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
EXCLUDED_STATUSES = {"Out", "Doubtful", "Questionable"}
MIN_GAMES = 5
MIN_AVERAGE_MINUTES = 10.0

def _get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ESPN player-data request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ESPN player-data response was not an object")
    return payload

def _walk_players(node: Any):
    if isinstance(node, dict):
        if node.get("id") is not None and (node.get("fullName") or node.get("displayName")):
            yield node
        for value in node.values():
            yield from _walk_players(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_players(value)

def fetch_roster(team: str) -> list[dict[str, Any]]:
    code = ALIASES.get(team.upper(), team.upper()).lower()
    payload = _get_json(f"{SITE}/teams/{urllib.parse.quote(code)}/roster")
    players = {}
    for raw in _walk_players(payload):
        pid = str(raw["id"])
        position = raw.get("position") or {}
        if isinstance(position, dict):
            position = position.get("abbreviation", "")
        players[pid] = {
            "id": pid,
            "name": raw.get("fullName") or raw.get("displayName"),
            "position": str(position or ""),
            "active": raw.get("active", True) is not False,
        }
    if not players:
        raise RuntimeError(f"ESPN roster returned no player records for {team}")
    return [players[key] for key in sorted(players)]

def _minutes(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "--", "DNP", "DND"):
        return None
    if ":" in text:
        try:
            minutes, seconds = text.split(":", 1)
            return float(minutes) + float(seconds) / 60
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None

def _stat_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "--", "DNP"):
        return None
    if "-" in text and text.count("-") == 1:
        text = text.split("-", 1)[0]
    try:
        return float(text)
    except ValueError:
        return None

def parse_gamelog(payload: dict[str, Any], player: dict[str, Any], cutoff: date | None = None) -> list[dict[str, Any]]:
    labels = [str(label).upper() for label in payload.get("labels", [])]
    index = {label: i for i, label in enumerate(labels)}
    # ESPN's game log uses labels such as MIN, REB, AST and PTS.
    required = {"MIN": "minutes", "REB": "rebounds", "AST": "assists", "PTS": "points"}
    if any(label not in index for label in required):
        raise ValueError(f"Player game log missing one of {', '.join(required)}")
    event_meta = payload.get("events", {})
    rows = []
    for season_type in payload.get("seasonTypes", []):
        name = str(season_type.get("displayName", "")).casefold()
        if name and "regular" not in name:
            continue
        for category in season_type.get("categories", []):
            for item in category.get("events", []):
                event_id = str(item.get("eventId", ""))
                event = event_meta.get(event_id, {})
                raw_date = event.get("gameDate") or event.get("date")
                try:
                    game_day = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
                except (AttributeError, ValueError):
                    continue
                if cutoff and game_day >= cutoff:
                    continue
                stats = item.get("stats") or []
                values = {key: _stat_number(stats[i] if i < len(stats) else None)
                          for label, key in required.items() for i in [index[label]]}
                mins = _minutes(values["minutes"])
                if mins is None or mins <= 0:
                    continue
                if any(values[k] is None for k in ("points", "rebounds", "assists")):
                    continue
                rows.append({
                    "date": game_day.isoformat(), "minutes": mins,
                    "points": values["points"], "rebounds": values["rebounds"],
                    "assists": values["assists"], "opponent": (event.get("opponent") or {}).get("abbreviation"),
                })
    # Avoid duplicate event rows if ESPN exposes multiple category blocks.
    deduped = {row["date"] + str(row["opponent"]): row for row in rows}
    return sorted(deduped.values(), key=lambda row: row["date"])

def fetch_player_gamelog(player_id: str, season: int, cutoff: date | None = None) -> list[dict[str, Any]]:
    url = f"{WEB}/athletes/{urllib.parse.quote(str(player_id))}/gamelog?season={int(season)}"
    payload = _get_json(url)
    return parse_gamelog(payload, {"id": player_id}, cutoff)

def project_player(player: dict[str, Any], games: list[dict[str, Any]], injury_status: str | None = None,
                   trials: int = 50000, seed: int = 42, lines: dict[str, float] | None = None) -> dict[str, Any] | None:
    import numpy as np
    if injury_status in EXCLUDED_STATUSES:
        return None
    if len(games) < MIN_GAMES:
        return None
    minutes = np.asarray([g["minutes"] for g in games], dtype=float)
    if float(np.mean(minutes)) < MIN_AVERAGE_MINUTES:
        return None
    recent = games[-10:]
    last5 = games[-5:]
    season_minutes = float(np.mean(minutes))
    recent_minutes = float(np.mean([g["minutes"] for g in last5]))
    projected_minutes = 0.65 * season_minutes + 0.35 * recent_minutes
    rng = np.random.default_rng(seed)
    projections = {}
    for stat in ("points", "rebounds", "assists"):
        season_total = sum(float(g[stat]) for g in games)
        season_rate = season_total / max(1e-9, sum(float(g["minutes"]) for g in games))
        recent_total = sum(float(g[stat]) for g in last5)
        recent_mins = sum(float(g["minutes"]) for g in last5)
        recent_rate = recent_total / max(1e-9, recent_mins)
        shrunk_rate = (season_rate * 8 + recent_rate * len(last5)) / (8 + len(last5))
        idx = rng.integers(0, len(recent), size=trials)
        sampled_minutes = np.asarray([recent[i]["minutes"] for i in idx], dtype=float)
        sampled_values = np.asarray([recent[i][stat] for i in idx], dtype=float)
        sampled_rate = sampled_values / np.maximum(sampled_minutes, 1e-9)
        rate_draw = 0.5 * sampled_rate + 0.5 * shrunk_rate
        minute_draw = 0.5 * sampled_minutes + 0.5 * projected_minutes
        distribution = np.maximum(0, rate_draw * minute_draw)
        line = (lines or {}).get(stat)
        projections[stat] = {
            "mean": float(np.mean(distribution)),
            "median": float(np.percentile(distribution, 50)),
            "p75": float(np.percentile(distribution, 75)),
            "line": line,
            "over_probability": float(np.mean(distribution > line) * 100) if line is not None else None,
            "under_probability": float(np.mean(distribution < line) * 100) if line is not None else None,
            "push_probability": float(np.mean(distribution == line) * 100) if line is not None else None,
        }
    projections["pra"] = {
        "mean": sum(projections[s]["mean"] for s in ("points", "rebounds", "assists")),
        "median": sum(projections[s]["median"] for s in ("points", "rebounds", "assists")),
        "p75": sum(projections[s]["p75"] for s in ("points", "rebounds", "assists")),
        "line": (lines or {}).get("pra"),
    }
    return {
        "player_id": player["id"], "player": player["name"], "position": player.get("position"),
        "games_used": len(games), "recent_games_used": len(recent),
        "season_minutes_avg": season_minutes, "recent5_minutes_avg": recent_minutes,
        "projected_minutes": projected_minutes, "injury_status": injury_status or "No designation in official report",
        "projections": projections,
        "warnings": ["Projected minutes are a recent/season statistical blend, not a confirmed rotation or starting-lineup projection."],
    }

def build_matchup_player_projections(home: str, away: str, game_date: date, season: int = 2027,
                                     trials: int = 50000, seed: int = 42) -> dict[str, Any]:
    injury = fetch_official_injuries(game_date, home, away, season)
    status_map = {(row["team"], row["player"].casefold()): row["status"] for row in injury["player_statuses"]}
    aliases = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}
    team_codes = [aliases.get(home.upper(), home.upper()), aliases.get(away.upper(), away.upper())]
    teams = {}
    warnings = list(injury["warnings"])
    for team_code in team_codes:
        if injury["team_submission"].get(team_code) == "NOT YET SUBMITTED":
            warnings.append(f"{team_code} injury report not submitted; player props withheld for this team.")
            teams[team_code] = []
            continue
        roster = fetch_roster(team_code)
        projections = []
        for player in roster:
            if not player["active"]:
                continue
            status = status_map.get((team_code, player["name"].casefold()))
            if status in EXCLUDED_STATUSES:
                continue
            try:
                time.sleep(0.25)
                games = fetch_player_gamelog(player["id"], season, game_date)
                projection = project_player(player, games, status, trials, seed + int(player["id"]) % 100000)
                if projection:
                    projections.append(projection)
            except (RuntimeError, ValueError) as exc:
                warnings.append(f"Skipped {player['name']} ({team_code}): {exc}")
        teams[team_code] = sorted(projections, key=lambda row: row["projected_minutes"], reverse=True)
    return {
        "game_date": game_date.isoformat(), "home": team_codes[0], "away": team_codes[1],
        "season": season, "trials_per_player": trials,
        "source": "ESPN public roster and player game logs plus NBA official injury report",
        "injury_report_url": injury["report_url"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "teams": teams, "warnings": warnings,
        "limitations": [
            "This is a statistical baseline, not a confirmed starting lineup or minutes/rotation model.",
            "No player usage, matchup-position defense, role change or teammate-absence impact is automatically inferred.",
            "Questionable, Doubtful and Out players are excluded; players absent from the report are not guaranteed to play.",
            "No sportsbook player-prop lines are included unless supplied separately.",
        ],
    }

def main():
    parser = argparse.ArgumentParser(description="Generate experimental NBA player points/rebounds/assists projections")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--season", type=int, default=2027)
    parser.add_argument("--trials", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="nba-player-projections.json")
    args = parser.parse_args()
    result = build_matchup_player_projections(args.home, args.away, date.fromisoformat(args.date), args.season, args.trials, args.seed)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
