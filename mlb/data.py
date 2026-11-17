"""Read-only MLB Stats API data access with explicit source provenance."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://statsapi.mlb.com/api/v1"


def get_json(url: str, timeout: float = 20.0) -> dict:
    request = Request(url, headers={
        "User-Agent": "DougsEliteMLB/1.0",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("MLB Stats API returned an unexpected response")
    return payload


def fetch_schedule(game_date: str) -> dict:
    """Fetch MLB games for YYYY-MM-DD with probable pitchers when published."""
    query = urlencode({"sportId": 1, "date": game_date,
                       "hydrate": "probablePitcher,linescore"})
    payload = get_json(f"{BASE}/schedule?{query}")
    games = []
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            teams = game.get("teams", {})
            home = teams.get("home", {})
            away = teams.get("away", {})
            games.append({
                "gamePk": game.get("gamePk"),
                "game_date": game.get("officialDate") or day.get("date"),
                "status": (game.get("status") or {}).get("detailedState"),
                "home": (home.get("team") or {}).get("name"),
                "away": (away.get("team") or {}).get("name"),
                "home_team_id": (home.get("team") or {}).get("id"),
                "away_team_id": (away.get("team") or {}).get("id"),
                "home_probable_pitcher": (home.get("probablePitcher") or {}).get("fullName"),
                "home_probable_pitcher_id": (home.get("probablePitcher") or {}).get("id"),
                "away_probable_pitcher": (away.get("probablePitcher") or {}).get("fullName"),
                "away_probable_pitcher_id": (away.get("probablePitcher") or {}).get("id"),
                "venue": (game.get("venue") or {}).get("name"),
            })
    return {"source": f"{BASE}/schedule", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "game_date": game_date, "games": games}


def fetch_player_stats(player_id: int, season: int, group: str) -> dict:
    if group not in {"hitting", "pitching"}:
        raise ValueError("group must be hitting or pitching")
    query = urlencode({"stats": "season", "group": group, "season": season})
    payload = get_json(f"{BASE}/people/{int(player_id)}/stats?{query}")
    blocks = payload.get("stats", [])
    splits = blocks[0].get("splits", []) if blocks else []
    if not splits:
        raise RuntimeError(f"No {group} season statistics returned for player {player_id}")
    stat = splits[0].get("stat", {})
    if not isinstance(stat, dict):
        raise RuntimeError(f"Invalid {group} statistics for player {player_id}")
    return {"player_id": int(player_id), "season": season, "group": group,
            "stat": stat, "source": f"{BASE}/people/{int(player_id)}/stats",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat()}
