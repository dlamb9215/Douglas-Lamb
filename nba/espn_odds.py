"""ESPN BET NBA odds adapter using ESPN's public Core API.

Provider ID 68 is ESPN BET. This module intentionally does not silently
substitute another sportsbook when ESPN BET has not posted a market.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

BASE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
ESPN_BET_PROVIDER_ID = 68


def _get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ESPN odds request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ESPN odds response was not a JSON object")
    return payload


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("+", ""))
    except (TypeError, ValueError):
        return None


def _american(value: Any) -> int | None:
    parsed = _number(value)
    if parsed is None or parsed == 0:
        return None
    return int(round(parsed))


def _items(payload: dict[str, Any]) -> list[Any]:
    items = payload.get("items")
    if isinstance(items, list):
        return items
    if isinstance(items, dict):
        return list(items.values())
    return []


def _resolve_odds_rows(event_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _items(payload):
        if isinstance(item, dict) and item.get("$ref"):
            row = _get_json(item["$ref"])
        elif isinstance(item, dict):
            row = item
        else:
            continue
        provider = row.get("provider") or {}
        provider_id = row.get("provider_id", row.get("providerId", provider.get("id")))
        try:
            provider_id = int(provider_id)
        except (TypeError, ValueError):
            provider_id = None
        if provider_id == ESPN_BET_PROVIDER_ID:
            rows.append(row)
    # Some ESPN responses return the selected record directly rather than an items envelope.
    if not rows and payload.get("provider_id") == ESPN_BET_PROVIDER_ID:
        rows.append(payload)
    return rows


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return None


def parse_espn_bet_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one ESPN BET odds record into the simulator's market schema."""
    home_ml = _american(_first(
        row, "home_team_odds_current_money_line_american",
        "home_team_odds_money_line", "homeMoneyLine"
    ))
    away_ml = _american(_first(
        row, "away_team_odds_current_money_line_american",
        "away_team_odds_money_line", "awayMoneyLine"
    ))
    home_spread = _number(_first(
        row, "home_team_odds_current_spread_value",
        "home_team_odds_current_point_spread_value",
        "home_team_odds_spread_value", "spread"
    ))
    total = _number(_first(row, "current_total_value", "over_under", "overUnder"))
    home_spread_price = _american(_first(
        row, "home_team_odds_current_spread_american", "home_team_odds_spread_odds"
    ))
    away_spread_price = _american(_first(
        row, "away_team_odds_current_spread_american", "away_team_odds_spread_odds"
    ))
    over_price = _american(_first(row, "current_over_american", "over_odds"))
    under_price = _american(_first(row, "current_under_american", "under_odds"))
    return {
        "home_ml_odds": home_ml,
        "away_ml_odds": away_ml,
        "home_spread": home_spread,
        "away_spread": -home_spread if home_spread is not None else None,
        "home_spread_odds": home_spread_price,
        "away_spread_odds": away_spread_price,
        "total": total,
        "over_odds": over_price,
        "under_odds": under_price,
        "opening_home_spread": _number(_first(
            row, "home_team_odds_open_spread_value",
            "home_team_odds_open_point_spread_value"
        )),
        "opening_total": _number(_first(row, "open_total_value")),
        "opening_home_ml_odds": _american(_first(
            row, "home_team_odds_open_money_line_american"
        )),
        "opening_away_ml_odds": _american(_first(
            row, "away_team_odds_open_money_line_american"
        )),
        "provider_id": ESPN_BET_PROVIDER_ID,
        "provider_name": str(row.get("provider_name") or "ESPN BET"),
        "last_updated": row.get("last_modified") or row.get("lastModified"),
    }


def fetch_espn_bet_odds(event_id: str) -> dict[str, Any]:
    """Fetch current ESPN BET markets for an ESPN NBA event ID."""
    event_id = str(event_id).strip()
    if not event_id:
        raise ValueError("An ESPN event ID is required for ESPN BET odds")
    url = f"{BASE}/events/{event_id}/competitions/{event_id}/odds?limit=100"
    payload = _get_json(url)
    rows = _resolve_odds_rows(event_id, payload)
    if not rows:
        raise RuntimeError(
            f"ESPN BET (provider {ESPN_BET_PROVIDER_ID}) has not posted odds for NBA event {event_id}; "
            "no other sportsbook was substituted."
        )
    parsed = [parse_espn_bet_row(row) for row in rows]
    # Prefer the most recently modified ESPN BET record when multiple snapshots exist.
    parsed.sort(key=lambda row: str(row.get("last_updated") or ""), reverse=True)
    result = parsed[0]
    result.update({
        "event_id": event_id,
        "source": "ESPN BET via ESPN Core API",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })
    return result
