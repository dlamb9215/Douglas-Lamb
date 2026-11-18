"""NHL game-day readiness gates for betting integrations.

Season-to-date goalie leaders are not confirmed starters. This contract
requires a current source-backed confirmation for both teams before an NHL
market adapter may set availability_confirmed=True.
"""
from __future__ import annotations

from datetime import datetime, timezone


def validate_confirmed_goalies(payload: dict, home: str, away: str, *, now=None,
                                max_age_hours: float = 3.0) -> dict:
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        raise ValueError("both NHL starting goalies must be explicitly confirmed")
    if str(payload.get("home", "")).upper() != home.upper() or str(payload.get("away", "")).upper() != away.upper():
        raise ValueError("goalie confirmation matchup does not match selected home/away teams")
    source = str(payload.get("source_url", "")).strip()
    if not source.startswith("https://"):
        raise ValueError("an HTTPS official team or league source is required")
    checked = str(payload.get("checked_at_utc", "")).strip()
    if not checked:
        raise ValueError("checked_at_utc is required")
    stamp = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("checked_at_utc must include a timezone")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    age = (current.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600
    if age < 0 or age > max_age_hours:
        raise ValueError("goalie confirmation is future-dated or older than the allowed window")
    goalies = payload.get("goalies")
    if not isinstance(goalies, dict):
        raise ValueError("goalies object is required")
    result = {}
    for side, team in (("home", home.upper()), ("away", away.upper())):
        item = goalies.get(side)
        if not isinstance(item, dict) or str(item.get("team", "")).upper() != team:
            raise ValueError(f"confirmed {side} goalie must match {team}")
        goalie_id = item.get("player_id")
        if isinstance(goalie_id, bool) or not isinstance(goalie_id, int) or goalie_id <= 0:
            raise ValueError(f"confirmed {side} goalie player_id must be a positive integer")
        if item.get("status") != "confirmed_starter":
            raise ValueError(f"{team} goalie must have status confirmed_starter")
        result[side] = {"team": team, "player_id": goalie_id, "status": "confirmed_starter"}
    return {
        "home": home.upper(), "away": away.upper(), "goalies": result,
        "source_url": source, "checked_at_utc": stamp.isoformat(),
        "age_hours": round(age, 2), "availability_confirmed": True,
    }


def validate_confirmed_skater_lineups(payload: dict, home: str, away: str, *, now=None,
                                       max_age_hours: float = 3.0,
                                       minimum_skaters: int = 18) -> dict:
    """Require fresh, source-backed active skater IDs and scratch lists for both teams."""
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        raise ValueError("both NHL skater lineups must be explicitly confirmed")
    if str(payload.get("home", "")).upper() != home.upper() or str(payload.get("away", "")).upper() != away.upper():
        raise ValueError("skater lineup matchup does not match selected home/away teams")
    source = str(payload.get("source_url", "")).strip()
    if not source.startswith("https://"):
        raise ValueError("an HTTPS official team or league source is required for skater lineups")
    checked = str(payload.get("checked_at_utc", "")).strip()
    if not checked:
        raise ValueError("checked_at_utc is required for skater lineups")
    stamp = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("skater lineup checked_at_utc must include a timezone")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    age = (current.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600
    if age < 0 or age > max_age_hours:
        raise ValueError("skater lineup confirmation is future-dated or stale")
    lineups = payload.get("lineups")
    if not isinstance(lineups, dict):
        raise ValueError("lineups object is required")
    normalized = {}
    for side, team in (("home", home.upper()), ("away", away.upper())):
        entry = lineups.get(side)
        if not isinstance(entry, dict) or str(entry.get("team", "")).upper() != team:
            raise ValueError(f"confirmed {side} skater lineup must match {team}")
        ids = entry.get("player_ids")
        if not isinstance(ids, list) or len(ids) < minimum_skaters:
            raise ValueError(f"{team} must have at least {minimum_skaters} confirmed active skaters")
        if any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in ids):
            raise ValueError(f"{team} lineup player IDs must be positive integers")
        if len(set(ids)) != len(ids):
            raise ValueError(f"{team} lineup contains duplicate player IDs")
        scratches = entry.get("scratched_player_ids", [])
        if not isinstance(scratches, list) or any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in scratches):
            raise ValueError(f"{team} scratched player IDs must be positive integers")
        if len(set(scratches)) != len(scratches) or set(ids).intersection(scratches):
            raise ValueError(f"{team} lineup has duplicate scratches or a scratched player marked active")
        normalized[side] = {"team": team, "player_ids": ids, "scratched_player_ids": scratches}
    return {"home": home.upper(), "away": away.upper(), "lineups": normalized,
            "source_url": source, "checked_at_utc": stamp.isoformat(),
            "age_hours": round(age, 2), "availability_confirmed": True}
