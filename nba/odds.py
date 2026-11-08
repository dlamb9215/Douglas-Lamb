"""The Odds API v4 adapter for NBA featured markets.

Requires ODDS_API_KEY. Requests only the main markets (moneyline, spread, total).
The provider is third-party; prices are snapshots, not guaranteed executable offers.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from statistics import median
from typing import Any

ENDPOINT = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"

def _american(value: Any) -> int:
    odds = int(round(float(value)))
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return odds

def _best(prices: list[int]) -> int | None:
    return max(prices) if prices else None

def fetch_events(api_key: str, regions: str = "us") -> tuple[list[dict[str, Any]], dict[str, str]]:
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("ODDS_API_KEY is missing. Add it in GitHub repository Settings > Secrets and variables > Actions.")
    params = urllib.parse.urlencode({
        "apiKey": key, "regions": regions, "markets": "h2h,spreads,totals",
        "oddsFormat": "american", "dateFormat": "iso",
    })
    request = urllib.request.Request(ENDPOINT + "?" + params, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
            headers = {
                "requests_remaining": response.headers.get("x-requests-remaining", ""),
                "requests_used": response.headers.get("x-requests-used", ""),
                "requests_last": response.headers.get("x-requests-last", ""),
            }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code == 401:
            raise RuntimeError("The Odds API rejected ODDS_API_KEY (HTTP 401). Check the repository secret.") from exc
        if exc.code == 429:
            raise RuntimeError("The Odds API quota/rate limit was reached (HTTP 429).") from exc
        raise RuntimeError(f"The Odds API request failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"The Odds API request failed: {exc}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("The Odds API response was not a list of events")
    return payload, headers

def matchup_odds(home_name: str, away_name: str, api_key: str | None = None) -> dict[str, Any]:
    events, quota = fetch_events(api_key or os.getenv("ODDS_API_KEY", ""))
    matches = [
        event for event in events
        if str(event.get("home_team", "")).casefold() == home_name.casefold()
        and str(event.get("away_team", "")).casefold() == away_name.casefold()
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one Odds API event for {away_name} at {home_name}; found {len(matches)}. "
            "Check team names and whether bookmakers have posted the game."
        )
    event = matches[0]
    moneyline = {"home": [], "away": []}
    spread_rows: list[tuple[float, int, int]] = []
    total_rows: list[tuple[float, int, int]] = []
    books = set()
    last_updates = []
    for book in event.get("bookmakers", []):
        book_key = book.get("key")
        if book_key:
            books.add(book_key)
        if book.get("last_update"):
            last_updates.append(book["last_update"])
        for market in book.get("markets", []):
            outcomes = market.get("outcomes", [])
            if market.get("key") == "h2h":
                for outcome in outcomes:
                    name = str(outcome.get("name", "")).casefold()
                    if name == home_name.casefold():
                        moneyline["home"].append(_american(outcome["price"]))
                    elif name == away_name.casefold():
                        moneyline["away"].append(_american(outcome["price"]))
            elif market.get("key") == "spreads":
                by_name = {str(o.get("name", "")).casefold(): o for o in outcomes}
                h = by_name.get(home_name.casefold())
                a = by_name.get(away_name.casefold())
                if h and a and h.get("point") is not None:
                    spread_rows.append((float(h["point"]), _american(h["price"]), _american(a["price"])))
            elif market.get("key") == "totals":
                by_name = {str(o.get("name", "")).casefold(): o for o in outcomes}
                over, under = by_name.get("over"), by_name.get("under")
                if over and under and over.get("point") is not None:
                    total_rows.append((float(over["point"]), _american(over["price"]), _american(under["price"])))
    result: dict[str, Any] = {
        "home_team": home_name, "away_team": away_name, "event_id": event.get("id"),
        "commence_time": event.get("commence_time"),
        "home_ml_odds": _best(moneyline["home"]), "away_ml_odds": _best(moneyline["away"]),
        "bookmakers": sorted(books), "bookmaker_count": len(books),
        "last_updated": max(last_updates) if last_updates else None,
        "source": "The Odds API v4", "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "quota": quota,
    }
    if spread_rows:
        line = float(median([row[0] for row in spread_rows]))
        at_line = [row for row in spread_rows if abs(row[0] - line) < 0.001]
        result.update({
            "home_spread": line,
            "away_spread": -line,
            "home_spread_odds": _best([row[1] for row in at_line]),
            "away_spread_odds": _best([row[2] for row in at_line]),
            "spread_book_count": len(at_line),
        })
    if total_rows:
        line = float(median([row[0] for row in total_rows]))
        at_line = [row for row in total_rows if abs(row[0] - line) < 0.001]
        result.update({
            "total": line,
            "over_odds": _best([row[1] for row in at_line]),
            "under_odds": _best([row[2] for row in at_line]),
            "total_book_count": len(at_line),
        })
    return result
