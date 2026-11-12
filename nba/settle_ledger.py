"""Settle archived NBA forecasts from completed ESPN scoreboard events.

The scoreboard is a third-party public feed. Event ID and team identities must
match the archived forecast before a result is recorded. No score is inferred.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from nba.schedule import fetch_scoreboard, normalize_team
from nba.prediction_ledger import FIELDS


def _score_event(event: dict[str, Any], scoreboard_day: date) -> dict[str, Any] | None:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    competition = competitions[0]
    teams: dict[str, dict[str, Any]] = {}
    for competitor in competition.get("competitors") or []:
        side = competitor.get("homeAway")
        team = competitor.get("team") or {}
        abbreviation = team.get("abbreviation")
        if side not in {"home", "away"} or not abbreviation:
            continue
        try:
            score = float(competitor.get("score"))
        except (TypeError, ValueError):
            score = None
        teams[side] = {"abbreviation": normalize_team(abbreviation), "score": score}
    if set(teams) != {"home", "away"}:
        return None
    status_obj = competition.get("status") or event.get("status") or {}
    status_type = status_obj.get("type") or {}
    state = str(status_type.get("state", "")).casefold()
    completed = status_type.get("completed") is True or state in {"post", "final"}
    return {"event_id": str(event.get("id", "")), "date": scoreboard_day.isoformat(),
            "home": teams["home"], "away": teams["away"], "completed": completed}


def settle_ledger(ledger_path: str, fetcher: Callable[[date], list[dict[str, Any]]] = fetch_scoreboard) -> dict[str, Any]:
    path = Path(ledger_path)
    if not path.exists():
        return {"status": "ledger_not_created_yet", "checked": 0, "settled": 0,
                "pending": 0, "errors": [], "ledger": str(path)}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError("ledger schema mismatch; refusing to settle")
        rows = list(reader)
    pending = [row for row in rows if not row.get("settled_at")]
    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in pending:
        day = row.get("game_date", "")
        if day:
            by_day.setdefault(day, []).append(row)
    settled = 0
    checked = 0
    errors: list[str] = []
    for day_text, day_rows in by_day.items():
        try:
            day = date.fromisoformat(day_text)
            events = fetcher(day)
        except Exception as exc:
            errors.append(f"{day_text}: scoreboard unavailable: {exc}")
            continue
        normalized = [_score_event(event, day) for event in events]
        normalized = [event for event in normalized if event]
        for row in day_rows:
            matches = [event for event in normalized if event["event_id"] == row.get("event_id")]
            if len(matches) != 1:
                errors.append(f"{row.get('forecast_id')}: expected one matching event ID; found {len(matches)}")
                continue
            event = matches[0]
            checked += 1
            if event["home"]["abbreviation"] != normalize_team(row["home_team"]) or event["away"]["abbreviation"] != normalize_team(row["away_team"]):
                errors.append(f"{row.get('forecast_id')}: event ID team mismatch (scoreboard {event['home']['abbreviation']} vs {event['away']['abbreviation']}; ledger {row['home_team']} vs {row['away_team']}); not settled")
                continue
            if not event["completed"] or event["home"]["score"] is None or event["away"]["score"] is None:
                continue
            row["actual_home"] = str(int(event["home"]["score"])) if float(event["home"]["score"]).is_integer() else str(event["home"]["score"])
            row["actual_away"] = str(int(event["away"]["score"])) if float(event["away"]["score"]).is_integer() else str(event["away"]["score"])
            row["settled_at"] = datetime.now(timezone.utc).isoformat()
            settled += 1
    if settled:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    return {"status": "updated" if settled else "no_completed_matches", "checked": checked,
            "settled": settled, "pending": sum(not row.get("settled_at") for row in rows),
            "errors": errors, "ledger": str(path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle completed NBA predictions in the versioned ledger")
    parser.add_argument("--ledger", default="nba/ledger/predictions.csv")
    args = parser.parse_args()
    print(json.dumps(settle_ledger(args.ledger), indent=2))


if __name__ == "__main__":
    main()
