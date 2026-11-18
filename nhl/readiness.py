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
