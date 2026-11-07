"""Refresh player season box-score and usage data from CFBD.

This cache is descriptive season data, not confirmed availability or depth-chart
information. A provider entitlement failure never erases a previously good cache.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .refresh import api_get


def refresh_player_data(year: int, season_type: str, api_key: str,
                        output_dir: str | Path = "ncaa/data") -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = []
    try:
        stats = api_get("/stats/player/season", {
            "year": year, "seasonType": season_type,
        }, api_key)
        if not isinstance(stats, list) or not stats:
            raise RuntimeError("CFBD player-season endpoint returned no player rows.")
    except RuntimeError as exc:
        warnings.append(f"Player season statistics unavailable: {exc}")
        stats = None

    try:
        usage = api_get("/player/usage", {
            "year": year, "excludeGarbageTime": "true",
        }, api_key)
        if not isinstance(usage, list):
            raise RuntimeError("CFBD player usage endpoint returned an unexpected response.")
    except RuntimeError as exc:
        warnings.append(f"Player usage metrics unavailable: {exc}")
        usage = None

    try:
        rosters = api_get("/roster", {"year": year, "classification": "fbs"}, api_key)
        if not isinstance(rosters, list) or not rosters:
            raise RuntimeError("CFBD roster endpoint returned no players.")
    except RuntimeError as exc:
        warnings.append(f"Current-season roster data unavailable: {exc}")
        rosters = None

    retrieved_at = datetime.now(timezone.utc).isoformat()
    status = {
        "provider": "CollegeFootballData",
        "year": year,
        "season_type": season_type,
        "retrieved_at": retrieved_at,
        "stats_available": bool(stats),
        "usage_available": bool(usage),
        "roster_available": bool(rosters),
        "warnings": warnings,
    }
    if stats:
        payload = {
            "metadata": status,
            "season_stats": stats,
            "usage": usage or [],
            "rosters": rosters or [],
        }
        destination = output_dir / "player_season_data.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(destination)
    status_path = output_dir / "player_data_status.json"
    status_temp = status_path.with_suffix(".json.tmp")
    status_temp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    status_temp.replace(status_path)
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh CFBD NCAA player season data")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--season-type", choices=("regular", "postseason", "both"), default="regular")
    parser.add_argument("--output-dir", default="ncaa/data")
    args = parser.parse_args()
    key = os.environ.get("CFBD_API_KEY", "").strip()
    if not key:
        raise SystemExit("CFBD_API_KEY is missing. Add it as a GitHub Actions secret.")
    status = refresh_player_data(args.year, args.season_type, key, args.output_dir)
    print(json.dumps(status, indent=2))
    if not status["stats_available"]:
        raise SystemExit("Player season data could not be refreshed; previous player cache was preserved.")


if __name__ == "__main__":
    main()
