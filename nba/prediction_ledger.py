"""Append immutable pregame NBA forecasts to a versioned prediction ledger.

Only predictions produced by a manual matchup run are archived. Results are not
settled here; settlement is a separate, auditable step after games finish.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELDS = [
    "forecast_id", "forecasted_at", "game_date", "game_start_time", "event_id", "home_team", "away_team",
    "git_sha", "workflow_run_id", "model_trials", "data_updated_at",
    "projected_home", "projected_away", "projected_total", "projected_margin",
    "home_win_probability", "away_win_probability",
    "spread_line", "home_cover_probability", "away_cover_probability",
    "total_line", "over_probability", "under_probability",
    "home_ml_odds", "away_ml_odds", "home_spread_odds", "away_spread_odds",
    "over_odds", "under_odds", "moneyline_bookmaker", "spread_bookmaker",
    "total_bookmaker", "moneyline_quote_at", "spread_quote_at", "total_quote_at",
    "odds_source", "availability_confirmed", "data_ready",
    "actual_home", "actual_away", "settled_at",
]

def build_row(payload: dict[str, Any], run_id: str, git_sha: str,
              forecasted_at: str | None = None) -> dict[str, Any]:
    result = payload.get("result") or {}
    projection = result.get("projection") or {}
    odds = payload.get("odds_context") or {}
    schedule = payload.get("schedule_context") or {}
    event = schedule.get("event") or {}
    probabilities = result
    timestamp = forecasted_at or datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("forecasted_at must be timezone-aware")
    home = str(payload.get("home_team") or "").upper()
    away = str(payload.get("away_team") or "").upper()
    if not home or not away or home == away:
        raise ValueError("forecast must contain two distinct NBA teams")
    if not result or "home_avg" not in result or "away_avg" not in result:
        raise ValueError("simulation result is missing final score projections")
    return {
        "forecast_id": f"{run_id}:{event.get('event_id') or payload.get('game_date') or ''}:{home}:{away}",
        "forecasted_at": parsed.astimezone(timezone.utc).isoformat(),
        "game_date": payload.get("game_date") or event.get("date") or "",
        "game_start_time": event.get("start_time") or "",
        "event_id": event.get("event_id") or "",
        "home_team": home, "away_team": away, "git_sha": git_sha,
        "workflow_run_id": str(run_id), "model_trials": result.get("trials", ""),
        "data_updated_at": payload.get("data_updated_at") or "",
        "projected_home": result.get("home_avg"), "projected_away": result.get("away_avg"),
        "projected_total": result.get("total_avg"),
        "projected_margin": result.get("home_avg", 0) - result.get("away_avg", 0),
        "home_win_probability": result.get("home_win"), "away_win_probability": result.get("away_win"),
        "spread_line": payload.get("spread_line"),
        "home_cover_probability": result.get("home_cover"),
        "away_cover_probability": result.get("away_cover"),
        "total_line": payload.get("total_line"),
        "over_probability": result.get("over"), "under_probability": result.get("under"),
        "home_ml_odds": payload.get("home_ml_odds"), "away_ml_odds": payload.get("away_ml_odds"),
        "home_spread_odds": payload.get("home_spread_odds"), "away_spread_odds": payload.get("away_spread_odds"),
        "over_odds": payload.get("over_odds"), "under_odds": payload.get("under_odds"),
        "moneyline_bookmaker": odds.get("moneyline_bookmaker"),
        "spread_bookmaker": odds.get("spread_bookmaker"),
        "total_bookmaker": odds.get("total_bookmaker"),
        "moneyline_quote_at": odds.get("moneyline_last_updated"),
        "spread_quote_at": odds.get("spread_last_updated"),
        "total_quote_at": odds.get("total_last_updated"),
        "odds_source": odds.get("source") or payload.get("odds_source") or "",
        "availability_confirmed": bool(payload.get("availability_confirmed")),
        "data_ready": bool(payload.get("data_ready")),
        "actual_home": "", "actual_away": "", "settled_at": "",
    }

def append_forecast(payload_path: str, ledger_path: str, run_id: str, git_sha: str) -> dict[str, Any]:
    raw_payload = Path(payload_path).read_text(encoding="utf-8").strip()
    # Accept the legacy literal backslash-n terminator from earlier simulator runs.
    if raw_payload.endswith("\\\\n"):
        raw_payload = raw_payload[:-2].rstrip()
    payload = json.loads(raw_payload)
    row = build_row(payload, run_id, git_sha)
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                raise ValueError("ledger schema mismatch; refusing to overwrite or append")
            existing = {item.get("forecast_id", "") for item in reader}
    if row["forecast_id"] in existing:
        return {"status": "duplicate", "forecast_id": row["forecast_id"], "path": str(path)}
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return {"status": "archived", "forecast_id": row["forecast_id"], "path": str(path)}

def main() -> None:
    parser = argparse.ArgumentParser(description="Archive a pregame NBA forecast")
    parser.add_argument("--payload", required=True)
    parser.add_argument("--ledger", default="nba/ledger/predictions.csv")
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--git-sha", default=os.getenv("GITHUB_SHA", "unknown"))
    args = parser.parse_args()
    print(json.dumps(append_forecast(args.payload, args.ledger, args.run_id, args.git_sha), indent=2))

if __name__ == "__main__":
    main()
