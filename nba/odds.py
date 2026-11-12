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
from collections import Counter
from typing import Any

ENDPOINT = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"

def _american(value: Any) -> int:
    odds = int(round(float(value)))
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return odds

def _best(prices: list[int]) -> int | None:
    return max(prices) if prices else None

def _implied_probability(price: int) -> float:
    return 100 / (price + 100) if price > 0 else (-price) / ((-price) + 100)

def _lowest_hold_pair(rows: list[tuple[int, int, str, str | None]]) -> tuple[int, int, str, str | None] | None:
    # Keep both sides and their timestamp from one bookmaker; never mix books.
    return min(rows, key=lambda row: (_implied_probability(row[0]) + _implied_probability(row[1]), row[2])) if rows else None

def _consensus_rows(rows: list[tuple[float, int, int, str, str | None]]) -> tuple[float, list[tuple[float, int, int, str, str | None]]]:
    counts = Counter(row[0] for row in rows)
    highest_count = max(counts.values())
    tied_lines = [line for line, count in counts.items() if count == highest_count]
    center = median([row[0] for row in rows])
    selected = min(tied_lines, key=lambda line: (abs(line - center), line))
    return float(selected), [row for row in rows if row[0] == selected]

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
    moneyline_rows: list[tuple[int, int, str, str | None]] = []
    spread_rows: list[tuple[float, int, int, str, str | None]] = []
    total_rows: list[tuple[float, int, int, str, str | None]] = []
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
                by_name = {str(o.get("name", "")).casefold(): o for o in outcomes}
                h = by_name.get(home_name.casefold())
                a = by_name.get(away_name.casefold())
                if h and a:
                    moneyline_rows.append((_american(h["price"]), _american(a["price"]), str(book_key or ""), book.get("last_update")))
            elif market.get("key") == "spreads":
                by_name = {str(o.get("name", "")).casefold(): o for o in outcomes}
                h = by_name.get(home_name.casefold())
                a = by_name.get(away_name.casefold())
                if h and a and h.get("point") is not None:
                    spread_rows.append((float(h["point"]), _american(h["price"]), _american(a["price"]), str(book_key or ""), book.get("last_update")))
            elif market.get("key") == "totals":
                by_name = {str(o.get("name", "")).casefold(): o for o in outcomes}
                over, under = by_name.get("over"), by_name.get("under")
                if over and under and over.get("point") is not None:
                    total_rows.append((float(over["point"]), _american(over["price"]), _american(under["price"]), str(book_key or ""), book.get("last_update")))
    ml_pair = _lowest_hold_pair(moneyline_rows)
    result: dict[str, Any] = {
        "home_team": home_name, "away_team": away_name, "event_id": event.get("id"),
        "commence_time": event.get("commence_time"),
        "home_ml_odds": ml_pair[0] if ml_pair else None,
        "away_ml_odds": ml_pair[1] if ml_pair else None,
        "moneyline_bookmaker": ml_pair[2] if ml_pair else None,
        "moneyline_last_updated": ml_pair[3] if ml_pair else None,
        "bookmakers": sorted(books), "bookmaker_count": len(books),
        "last_updated": max(last_updates) if last_updates else None,
        "source": "The Odds API v4", "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "quota": quota,
    }
    if spread_rows:
        line, at_line = _consensus_rows(spread_rows)
        pair = _lowest_hold_pair([(row[1], row[2], row[3], row[4]) for row in at_line])
        result.update({
            "home_spread": line,
            "away_spread": -line,
            "home_spread_odds": pair[0] if pair else None,
            "away_spread_odds": pair[1] if pair else None,
            "spread_bookmaker": pair[2] if pair else None,
            "spread_last_updated": pair[3] if pair else None,
            "spread_book_count": len(at_line),
        })
    if total_rows:
        line, at_line = _consensus_rows(total_rows)
        pair = _lowest_hold_pair([(row[1], row[2], row[3]) for row in at_line])
        result.update({
            "total": line,
            "over_odds": pair[0] if pair else None,
            "under_odds": pair[1] if pair else None,
            "total_bookmaker": pair[2] if pair else None,
            "total_last_updated": pair[3] if pair else None,
            "total_book_count": len(at_line),
        })
    return result
