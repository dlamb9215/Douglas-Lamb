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

from nba.schedule import fetch_scoreboard, _event_row
from nba.prediction_ledger import FIELDS


def settle_ledger(ledger_path: str, fetcher: Callable[[date], list[dict[str, Any]]] = fetch_scoreboard) -> dict[str, Any]:
    path = Path(ledger_path)
    if not path.exists():
        raise FileNotFoundError(f"Prediction ledger not found: {path}")
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
        normalized = [_event_row(event, day) for event in events]
        normalized = [event for event in normalized if event]
        for row in day_rows:
            matches = [event for event in normalized if event["event_id"] == row.get("event_id")]
            if len(matches) != 1:
                errors.append(f"{row.get('forecast_id')}: expected one matching event ID; found {len(matches)}")
                continue
            event = matches[0]
            checked += 1
            if event["home"]["abbreviation"] != row["home_team"] or event["away"]["abbreviation"] != row["away_team"]:
                errors.append(f"{row.get('forecast_id')}: event ID team mismatch; not settled")
                continue
            if not event["completed"] or event["home"]["score"] is None or event["away"]["score"] is None:
                continue
            row["actual_home"] = str(event["home"]["score"])
            row["actual_away"] = str(event["away"]["score"])
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
