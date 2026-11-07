"""Validation for manually supplied sportsbook market snapshots."""
import math
from datetime import datetime, timezone, timedelta


def validate_market_snapshot(values, source=None, checked_at=None,
                             max_age_hours=6, now=None):
    market_fields = ("spread", "total", "home_odds", "away_odds",
                     "over_odds", "under_odds")
    supplied = {}
    for field in market_fields:
        value = values.get(field)
        if value is None or value == "":
            supplied[field] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric.")
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite.")
        if field.endswith("_odds") and value == 0:
            raise ValueError(f"{field} cannot be zero American odds.")
        supplied[field] = float(value)
    has_market = any(value is not None for value in supplied.values())
    if not has_market:
        return {"valid": True, "provided": False, "source": None, "checked_at_utc": None}
    if not source or not str(source).strip():
        raise ValueError("A sportsbook source is required when market lines are supplied.")
    if not checked_at:
        raise ValueError("An ISO-8601 odds_checked_at timestamp is required when market lines are supplied.")
    try:
        timestamp = datetime.fromisoformat(str(checked_at).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("odds_checked_at must be ISO-8601.") from exc
    if timestamp.tzinfo is None:
        raise ValueError("odds_checked_at must include a timezone.")
    now = now or datetime.now(timezone.utc)
    age = now - timestamp.astimezone(timezone.utc)
    if age < timedelta(minutes=-5) or age > timedelta(hours=max_age_hours):
        raise ValueError(f"Sportsbook snapshot is future-dated or older than {max_age_hours} hours.")
    return {
        "valid": True, "provided": True, "source": str(source).strip(),
        "checked_at_utc": timestamp.astimezone(timezone.utc).isoformat(),
        "max_age_hours": max_age_hours, "lines": supplied,
    }
