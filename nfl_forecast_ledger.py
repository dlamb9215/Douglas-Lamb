"""Persistent NFL forecast ledger and settled-result calibration.

Forecasts are appended before kickoff. Reconciliation reads completed games
from nflverse schedules; metrics are descriptive and never self-certify model
calibration or betting readiness.
"""
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    "run_id", "recorded_at_utc", "season", "week", "home_team", "away_team",
    "kickoff", "trials", "seed", "home_win_probability", "away_win_probability",
    "home_spread", "home_cover_probability", "away_cover_probability",
    "total_line", "over_probability", "under_probability",
    "home_moneyline_odds", "away_moneyline_odds", "over_odds", "under_odds",
    "weather_available", "weather_wind_mph", "weather_precipitation_mm_per_hour",
    "pregame_verified", "actual_home_score", "actual_away_score", "settled_at_utc",
]


def append_forecast(record, path="nfl_forecast_ledger.csv"):
    required = ("run_id", "home_team", "away_team", "home_win_probability", "away_win_probability")
    if any(record.get(key) in (None, "") for key in required):
        raise ValueError("Forecast record is missing required identifiers or win probabilities.")
    if record["home_team"] == record["away_team"]:
        raise ValueError("Home and away teams must differ.")
    for key in ("home_win_probability", "away_win_probability"):
        value = float(record[key])
        if not 0 <= value <= 100:
            raise ValueError(f"{key} must be between 0 and 100.")
    target = Path(path)
    rows = []
    if target.exists():
        with target.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if any(row.get("run_id") == str(record["run_id"]) for row in rows):
            return False
    normalized = {field: record.get(field, "") for field in FIELDS}
    normalized["recorded_at_utc"] = normalized["recorded_at_utc"] or datetime.now(timezone.utc).isoformat()
    write_header = not target.exists() or target.stat().st_size == 0
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(normalized)
    return True


def reconcile_results(schedule_rows, path="nfl_forecast_ledger.csv"):
    target = Path(path)
    if not target.exists():
        return {"settled": 0, "unsettled": 0}
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    games = {}
    for game in schedule_rows:
        if game.get("game_type") not in {"REG", "POST"}:
            continue
        key = (str(game.get("season")), str(game.get("week")),
               str(game.get("home_team")), str(game.get("away_team")))
        if game.get("home_score") not in ("", None) and game.get("away_score") not in ("", None):
            games[key] = (game["home_score"], game["away_score"])
    now = datetime.now(timezone.utc).isoformat()
    settled = 0
    for row in rows:
        if row.get("settled_at_utc") or not row.get("week") or not row.get("season"):
            continue
        if row.get("week"):
            key = (str(row["season"]), str(row["week"]), row["home_team"], row["away_team"])
            score = games.get(key)
        else:
            matches = [
                value for game_key, value in games.items()
                if game_key[0] == str(row["season"])
                and game_key[2] == row["home_team"]
                and game_key[3] == row["away_team"]
            ]
            score = matches[0] if len(matches) == 1 else None
        if score is None:
            continue
        row["actual_home_score"], row["actual_away_score"] = score
        row["settled_at_utc"] = now
        settled += 1
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {"settled": settled, "unsettled": sum(not row.get("settled_at_utc") for row in rows)}


def calibration_summary(path="nfl_forecast_ledger.csv"):
    target = Path(path)
    if not target.exists():
        return {"settled_games": 0, "status": "NO_LEDGER"}
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    settled = [r for r in rows if r.get("settled_at_utc") and r.get("actual_home_score") not in ("", None)]
    if not settled:
        return {"settled_games": 0, "status": "NO_SETTLED_GAMES"}
    outcomes = [1 if float(r["actual_home_score"]) > float(r["actual_away_score"]) else 0
                for r in settled]
    probabilities = [float(r["home_win_probability"]) / 100 for r in settled]
    brier = sum((p-y)**2 for p, y in zip(probabilities, outcomes)) / len(settled)
    spread_rows = [
        r for r in settled
        if r.get("home_spread") not in ("", None)
        and r.get("home_cover_probability") not in ("", None)
        and float(r["actual_home_score"]) - float(r["actual_away_score"]) + float(r["home_spread"]) != 0
    ]
    spread_brier = None
    spread_accuracy = None
    if spread_rows:
        spread_outcomes = [
            1 if float(r["actual_home_score"]) - float(r["actual_away_score"]) + float(r["home_spread"]) > 0 else 0
            for r in spread_rows
        ]
        spread_probs = [float(r["home_cover_probability"]) / 100 for r in spread_rows]
        spread_brier = sum((p-y)**2 for p, y in zip(spread_probs, spread_outcomes)) / len(spread_rows)
        spread_accuracy = sum((p >= 0.5) == bool(y) for p, y in zip(spread_probs, spread_outcomes)) / len(spread_rows)
    total_rows = [
        r for r in settled
        if r.get("total_line") not in ("", None)
        and r.get("over_probability") not in ("", None)
        and float(r["actual_home_score"]) + float(r["actual_away_score"]) != float(r["total_line"])
    ]
    total_brier = None
    total_accuracy = None
    if total_rows:
        total_outcomes = [
            1 if float(r["actual_home_score"]) + float(r["actual_away_score"]) > float(r["total_line"]) else 0
            for r in total_rows
        ]
        total_probs = [float(r["over_probability"]) / 100 for r in total_rows]
        total_brier = sum((p-y)**2 for p, y in zip(total_probs, total_outcomes)) / len(total_rows)
        total_accuracy = sum((p >= 0.5) == bool(y) for p, y in zip(total_probs, total_outcomes)) / len(total_rows)
    return {
        "settled_games": len(settled),
        "home_win_brier_score": round(brier, 6),
        "spread_brier_score": round(spread_brier, 6) if spread_brier is not None else None,
        "spread_decision_accuracy": round(spread_accuracy, 4) if spread_accuracy is not None else None,
        "spread_sample_size": len(spread_rows),
        "total_brier_score": round(total_brier, 6) if total_brier is not None else None,
        "total_decision_accuracy": round(total_accuracy, 4) if total_accuracy is not None else None,
        "total_sample_size": len(total_rows),
        "status": "INSUFFICIENT_SAMPLE" if len(settled) < 100 else "REVIEW_REQUIRED",
        "calibrated": False,
        "note": "Use time-ordered out-of-sample seasons and market-specific calibration before enabling betting thresholds.",
    }


def main():
    import argparse
    from nfl_weather import _get_rows, SCHEDULE_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="nfl_forecast_ledger.csv")
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    if args.reconcile:
        print(json.dumps(reconcile_results(_get_rows(SCHEDULE_URL), args.ledger), indent=2))
    if args.summary or not args.reconcile:
        print(json.dumps(calibration_summary(args.ledger), indent=2))


if __name__ == "__main__":
    main()
