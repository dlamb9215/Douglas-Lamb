"""Strict game-day confirmation overlay for final player projections.

The nflverse depth chart is a roster/workload source, not official inactive
confirmation. This module requires an explicitly reviewed confirmation file.
"""
from datetime import datetime, timezone, timedelta


def validate_confirmation_file(data, max_age_hours=24):
    if not isinstance(data, dict) or not isinstance(data.get("players"), list):
        raise ValueError("Confirmation file must contain a players list.")
    checked = data.get("checked_at_utc")
    source = data.get("source")
    if not checked or not source:
        raise ValueError("Confirmation file requires source and checked_at_utc.")
    try:
        timestamp = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("checked_at_utc must be ISO-8601.") from exc
    if timestamp.tzinfo is None:
        raise ValueError("checked_at_utc must include a timezone.")
    age = datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)
    if age < timedelta(minutes=-5) or age > timedelta(hours=max_age_hours):
        raise ValueError("Game-day confirmation file is stale or future-dated.")
    seen = set()
    normalized = {}
    for row in data["players"]:
        if not isinstance(row, dict):
            raise ValueError("Each confirmation must be an object.")
        name, team = row.get("name"), row.get("team")
        status, starter = row.get("status"), row.get("starter")
        if not name or not team or status not in {"active", "inactive", "out"}:
            raise ValueError("Each confirmation needs name, team and valid status.")
        if not isinstance(starter, bool):
            raise ValueError("starter must be true or false.")
        key = (team.upper(), name.strip().casefold())
        if key in seen:
            raise ValueError(f"Duplicate game-day confirmation: {team} {name}")
        seen.add(key)
        normalized[key] = {
            "status": status, "starter": starter,
            "note": row.get("note", ""),
        }
    return normalized


def validate_team_market_confirmation(data, home_team, away_team, minimum_starters=22):
    """Require an explicit full inactive review and 22 confirmed active starters per team."""
    try:
        normalized = validate_confirmation_file(data)
    except ValueError as exc:
        return False, str(exc)
    if data.get("all_inactives_reviewed") is not True:
        return False, "all_inactives_reviewed must be explicitly true"
    source_url = str(data.get("source_url", "")).strip()
    if not source_url.startswith("https://"):
        return False, "official game-day source_url is required"
    for team in (home_team.upper(), away_team.upper()):
        starters = [
            record for (team_code, _), record in normalized.items()
            if team_code == team and record["status"] == "active" and record["starter"] is True
        ]
        if len(starters) < minimum_starters:
            return False, f"{team} has {len(starters)} confirmed active starters; {minimum_starters} are required"
    return True, "fresh full inactive review and 22 confirmed active starters per team"


def confirmed_player_copy(player, confirmations):
    """Return a safe projection copy only for explicitly active starters."""
    key = (str(player.get("team", "")).upper(),
           str(player.get("name", "")).strip().casefold())
    record = confirmations.get(key)
    if not record or record["status"] != "active" or not record["starter"]:
        return None
    result = dict(player)
    result["status"] = "active"
    result["starter"] = True
    result["game_day_confirmation"] = record
    return result
