"""Match timestamped forecasts to completed CFBD game results."""
from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from .data.refresh import api_get
from .forecast_ledger import FIELDS


def reconcile_ledger(path: str | Path, year: int, api_key: str) -> dict:
    path = Path(path)
    if not path.exists():
        return {"updated": 0, "reason": "forecast ledger not found"}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError("Forecast ledger schema mismatch")
        rows = list(reader)
    games = api_get("/games", {
        "year": year, "seasonType": "both", "classification": "fbs",
    }, api_key)
    if not isinstance(games, list):
        raise RuntimeError("CFBD games endpoint returned unexpected data")
    candidates = []
    for game in games:
        if game.get("homePoints") is None or game.get("awayPoints") is None:
            continue
        if not game.get("homeTeam") or not game.get("awayTeam") or not game.get("startDate"):
            continue
        try:
            start = datetime.fromisoformat(str(game["startDate"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        candidates.append((game, start.astimezone(timezone.utc)))

    updated = 0
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for row in rows:
        if row.get("pregame_status") != "pregame" or row.get("home_win"):
            continue
        try:
            kickoff = datetime.fromisoformat(row["kickoff"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if kickoff.tzinfo is None:
            continue
        kickoff = kickoff.astimezone(timezone.utc)
        matches = []
        for game, start in candidates:
            if (str(game["homeTeam"]).casefold() != row["home_team"].casefold()
                    or str(game["awayTeam"]).casefold() != row["away_team"].casefold()):
                continue
            delta = abs((start - kickoff).total_seconds())
            if delta <= 48 * 3600:
                matches.append((delta, game))
        if not matches:
            continue
        game = min(matches, key=lambda item: item[0])[1]
        home_score, away_score = int(game["homePoints"]), int(game["awayPoints"])
        margin = home_score - away_score
        total_score = home_score + away_score
        row["actual_home_score"] = home_score
        row["actual_away_score"] = away_score
        row["home_win"] = 1 if margin > 0 else 0
        if row.get("home_spread") not in (None, ""):
            adjusted = margin + float(row["home_spread"])
            row["home_cover"] = 1 if adjusted > 0 else (0 if adjusted < 0 else "")
        if row.get("total_line") not in (None, ""):
            line = float(row["total_line"])
            row["over"] = 1 if total_score > line else (0 if total_score < line else "")
        row["outcome_source"] = "CollegeFootballData games API"
        row["outcome_retrieved_at"] = retrieved_at
        updated += 1

    if updated:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    return {"updated": updated, "total_forecasts": len(rows),
            "outcome_source": "CollegeFootballData games API"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile NCAA forecast ledger with final scores")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--input", default="ncaa/forecast_ledger.csv")
    args = parser.parse_args()
    key = os.environ.get("CFBD_API_KEY", "").strip()
    if not key:
        raise SystemExit("CFBD_API_KEY is missing.")
    print(reconcile_ledger(args.input, args.year, key))


if __name__ == "__main__":
    main()
