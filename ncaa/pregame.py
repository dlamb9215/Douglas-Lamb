"""Validate explicitly sourced pregame checks without inventing live data."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

REQUIRED = ("home_starting_qb", "away_starting_qb", "home_injuries",
            "away_injuries", "weather", "sportsbook")


def load_pregame_checks(path: str | Path, home: str, away: str, *,
                        require_verified: bool = False,
                        aliases: dict[str, str] | None = None) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Pregame checks must be a JSON object")
    aliases = aliases or {}
    raw_home = aliases.get(str(raw.get("home_team", "")).casefold(), raw.get("home_team", ""))
    raw_away = aliases.get(str(raw.get("away_team", "")).casefold(), raw.get("away_team", ""))
    if str(raw_home).casefold() != home.casefold():
        raise ValueError("Pregame home team does not match simulation")
    if str(raw_away).casefold() != away.casefold():
        raise ValueError("Pregame away team does not match simulation")
    checks = raw.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("Pregame checks must contain a checks object")
    missing = []
    validated = {}
    for field in REQUIRED:
        entry = checks.get(field)
        if not isinstance(entry, dict):
            missing.append(field)
            continue
        verified = entry.get("verified") is True
        source = entry.get("source")
        checked_at = entry.get("checked_at")
        if verified:
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f"{field}: verified entry requires source")
            if not isinstance(checked_at, str):
                raise ValueError(f"{field}: verified entry requires timestamp")
            try:
                timestamp = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"{field}: invalid timestamp") from exc
            if timestamp.tzinfo is None:
                raise ValueError(f"{field}: timestamp must include timezone")
            age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
            if age < -300 or age > 86400:
                raise ValueError(f"{field}: check must be within last 24 hours")
        else:
            missing.append(field)
        validated[field] = entry
    if require_verified and missing:
        raise ValueError("Unverified pregame checks: " + ", ".join(missing))
    return {
        "home_team": home,
        "away_team": away,
        "checks": validated,
        "all_verified": not missing,
        "unverified": missing,
        "warning": ("Verified means user/provider-supplied with source and timestamp; "
                    "the simulator does not independently authenticate sources."),
    }
