"""Append timestamped pregame forecasts for later calibration."""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    "run_id", "recorded_at", "kickoff", "pregame_status", "season",
    "home_team", "away_team", "trials", "seed",
    "home_win_probability", "home_spread", "home_cover_probability",
    "total_line", "over_probability", "home_moneyline_odds", "away_moneyline_odds",
    "over_odds", "under_odds", "home_data_as_of", "away_data_as_of",
    "player_projection_count", "data_warnings", "actual_home_score", "actual_away_score",
    "home_win", "home_cover", "over", "outcome_source", "outcome_retrieved_at",
]


def append_forecast(result: dict, path: str | Path, kickoff: str | None = None,
                    run_id: str | None = None,
                    recorded_at: datetime | None = None) -> dict:
    recorded_at = recorded_at or datetime.now(timezone.utc)
    if recorded_at.tzinfo is None:
        raise ValueError("recorded_at must be timezone-aware")
    kickoff_value = ""
    status = "unknown"
    if kickoff:
        try:
            kickoff_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("kickoff must be an ISO-8601 timestamp") from exc
        if kickoff_dt.tzinfo is None:
            raise ValueError("kickoff must include a timezone")
        kickoff_value = kickoff_dt.astimezone(timezone.utc).isoformat()
        status = "pregame" if kickoff_dt > recorded_at else "postgame"

    market = result.get("market", {})
    sportsbook = result.get("sportsbook_analysis", {})
    moneyline = sportsbook.get("moneyline", {})
    total = sportsbook.get("total", {})
    quality = result.get("data_quality", {})
    profiles = result.get("profiles", {})
    prices = result.get("market_prices", {})
    row = {
        "run_id": str(run_id or os.environ.get("GITHUB_RUN_ID") or
                      f"{result.get('seed', '')}-{recorded_at.isoformat()}"),
        "recorded_at": recorded_at.astimezone(timezone.utc).isoformat(),
        "kickoff": kickoff_value,
        "pregame_status": status,
        "season": result.get("season", ""),
        "home_team": result.get("home_team", ""),
        "away_team": result.get("away_team", ""),
        "trials": result.get("trials", ""),
        "seed": result.get("seed", ""),
        "home_win_probability": result.get("home_win_probability", ""),
        "home_spread": market.get("home_spread", ""),
        "home_cover_probability": market.get("home_cover_probability", ""),
        "total_line": market.get("total_line", ""),
        "over_probability": market.get("over_probability", ""),
        "home_moneyline_odds": prices.get("home_moneyline", ""),
        "away_moneyline_odds": prices.get("away_moneyline", ""),
        "over_odds": prices.get("over", ""),
        "under_odds": prices.get("under", ""),
        "home_data_as_of": profiles.get(result.get("home_team"), {}).get("as_of", ""),
        "away_data_as_of": profiles.get(result.get("away_team"), {}).get("as_of", ""),
        "player_projection_count": len(result.get("player_projections", [])),
        "data_warnings": " | ".join(quality.get("warnings", [])),
        "actual_home_score": "", "actual_away_score": "",
        "home_win": "", "home_cover": "", "over": "",
        "outcome_source": "", "outcome_retrieved_at": "",
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if path.exists() and path.stat().st_size:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                raise ValueError("Forecast ledger schema mismatch; migrate the ledger before appending")
            existing = list(reader)
    if any(item.get("run_id") == row["run_id"] for item in existing):
        return {"appended": False, "run_id": row["run_id"], "reason": "duplicate run_id"}
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not existing:
            writer.writeheader()
        writer.writerow(row)
    return {"appended": True, "run_id": row["run_id"], "pregame_status": status}
