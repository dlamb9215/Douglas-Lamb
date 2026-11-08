"""ESPN public NBA scoreboard adapter for verified matchup and rest context.

ESPN's site scoreboard is an undocumented public feed, not an official supported API.
Use low request volume, short timeouts and explicit source/timestamp metadata.
No injury status or travel distance is inferred by this module.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ALIASES = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}
REVERSE = {v: k for k, v in ALIASES.items()}

def normalize_team(code: str) -> str:
    value = str(code).strip().upper()
    return ALIASES.get(value, value)

def _get_json(url: str, retries: int = 3, timeout: int = 20) -> dict[str, Any]:
    last_error = None
    for attempt in range(retries):
        try:
            # Do not spoof a browser user-agent; ESPN's public feed has blocked that in some environments.
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"ESPN scoreboard returned HTTP {response.status}")
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
                raise RuntimeError("ESPN scoreboard response has no events list")
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"ESPN scoreboard request failed after {retries} attempts: {last_error}")

def fetch_scoreboard(day: date) -> list[dict[str, Any]]:
    url = f"{BASE}?dates={day:%Y%m%d}"
    return _get_json(url)["events"]

def _event_row(event: dict[str, Any]) -> dict[str, Any] | None:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    comp = competitions[0]
    competitors = comp.get("competitors") or []
    teams = {}
    for competitor in competitors:
        side = competitor.get("homeAway")
        team = competitor.get("team") or {}
        if side in ("home", "away") and team.get("abbreviation"):
            teams[side] = {
                "abbreviation": normalize_team(team["abbreviation"]),
                "name": team.get("displayName", team.get("name", team["abbreviation"])),
                "score": _number_or_none(competitor.get("score")),
            }
    if set(teams) != {"home", "away"}:
        return None
    status = (comp.get("status") or event.get("status") or {}).get("type") or {}
    start = comp.get("date") or event.get("date")
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    venue = comp.get("venue") or {}
    return {
        "event_id": str(event.get("id", "")),
        "date": start_dt.date().isoformat(),
        "start_time": start_dt.astimezone(timezone.utc).isoformat(),
        "home": teams["home"],
        "away": teams["away"],
        "status": status.get("state", "unknown"),
        "completed": bool(status.get("completed", False)),
        "venue": venue.get("fullName"),
        "venue_city": (venue.get("address") or {}).get("city"),
        "neutral_site": bool(comp.get("neutralSite", False)),
        "source": "ESPN public NBA scoreboard",
    }

def _number_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def build_context(home: str, away: str, game_date: date, lookback_days: int = 10) -> dict[str, Any]:
    home_code, away_code = normalize_team(home), normalize_team(away)
    if home_code == away_code:
        raise ValueError("Home and away teams must differ")
    if not 1 <= lookback_days <= 30:
        raise ValueError("lookback_days must be between 1 and 30")

    events: list[dict[str, Any]] = []
    # Fetch each calendar day separately to avoid relying on undocumented range semantics.
    for offset in range(lookback_days, -1, -1):
        day = game_date - timedelta(days=offset)
        if offset != lookback_days:
            time.sleep(0.25)
        events.extend(_event_row(event) for event in fetch_scoreboard(day))
    events = [row for row in events if row]
    candidates = [
        row for row in events
        if row["date"] == game_date.isoformat()
        and row["home"]["abbreviation"] == home_code
        and row["away"]["abbreviation"] == away_code
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one ESPN schedule event for {away_code} at {home_code} "
            f"on {game_date.isoformat()}, found {len(candidates)}"
        )
    target = candidates[0]
    result = {
        "event": target,
        "home_rest_days": None,
        "away_rest_days": None,
        "home_travel_miles": None,
        "away_travel_miles": None,
        "source": "ESPN public NBA scoreboard",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "warnings": [
            "ESPN scoreboard does not provide official injury/inactive status in this context.",
            "Travel miles are not estimated because arena coordinates and travel itinerary are not verified.",
        ],
    }
    for side, code in (("home", home_code), ("away", away_code)):
        previous = [
            row for row in events
            if row["completed"] and row["date"] < game_date.isoformat()
            and code in (row["home"]["abbreviation"], row["away"]["abbreviation"])
        ]
        if previous:
            last = max(previous, key=lambda row: (row["date"], row["start_time"]))
            last_day = date.fromisoformat(last["date"])
            result[f"{side}_rest_days"] = max(0, (game_date - last_day).days - 1)
        else:
            result["warnings"].append(f"No completed prior game found for {code} in the {lookback_days}-day lookback.")
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch NBA matchup schedule and rest context from ESPN")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--date", required=True, help="Game date YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=10)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    context = build_context(args.home, args.away, date.fromisoformat(args.date), args.lookback_days)
    rendered = json.dumps(context, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

if __name__ == "__main__":
    main()
