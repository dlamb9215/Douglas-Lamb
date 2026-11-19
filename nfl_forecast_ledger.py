"""Persistent NFL forecast ledger and settled-result calibration.

Forecasts are appended before kickoff. Reconciliation reads completed games
from nflverse schedules; metrics are descriptive and never self-certify model
calibration or betting readiness.
"""
import csv
import json
import os
import math
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    "run_id", "recorded_at_utc", "season", "week", "home_team", "away_team",
    "kickoff", "trials", "seed", "home_win_probability", "away_win_probability",
    "home_spread", "home_cover_probability", "away_cover_probability",
    "total_line", "over_probability", "under_probability",
    "home_moneyline_odds", "away_moneyline_odds", "over_odds", "under_odds",
    "weather_available", "weather_wind_mph", "weather_precipitation_mm_per_hour",
    "pregame_verified", "sportsbook_source", "odds_checked_at_utc",
    "actual_home_score", "actual_away_score", "settled_at_utc",
]


def append_forecast(record, path="nfl_forecast_ledger.csv"):
    required = ("run_id", "home_team", "away_team", "home_win_probability", "away_win_probability")
    if any(record.get(key) in (None, "") for key in required):
        raise ValueError("Forecast record is missing required identifiers or win probabilities.")
    home, away = str(record["home_team"]).strip().upper(), str(record["away_team"]).strip().upper()
    if not home or not away or home == away:
        raise ValueError("Home and away teams must be distinct non-empty abbreviations.")
    probability_fields = ("home_win_probability", "away_win_probability",
                          "home_cover_probability", "away_cover_probability",
                          "over_probability", "under_probability")
    probs = {}
    for key in probability_fields:
        raw = record.get(key)
        if raw in (None, ""):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a finite percentage from 0 to 100.") from exc
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f"{key} must be a finite percentage from 0 to 100.")
        probs[key] = value
    moneyline_total = probs["home_win_probability"] + probs["away_win_probability"]
    if moneyline_total <= 0 or moneyline_total > 101:
        raise ValueError("Moneyline probabilities must sum to a positive value no greater than 100% after allowing for ties.")
    if "home_cover_probability" in probs and "away_cover_probability" in probs:
        spread_total = probs["home_cover_probability"] + probs["away_cover_probability"]
        if spread_total <= 0 or spread_total > 101:
            raise ValueError("Spread probabilities must sum to a positive value no greater than 100% after allowing for pushes.")
    if "over_probability" in probs and "under_probability" in probs:
        total_market = probs["over_probability"] + probs["under_probability"]
        if total_market <= 0 or total_market > 101:
            raise ValueError("Over/under probabilities must sum to a positive value no greater than 100% after allowing for pushes.")
    odds_fields = ("home_moneyline_odds", "away_moneyline_odds", "over_odds", "under_odds")
    if any(record.get(key) not in (None, "") for key in odds_fields):
        source = str(record.get("sportsbook_source") or "").strip()
        checked = str(record.get("odds_checked_at_utc") or "").strip()
        if not source or not checked:
            raise ValueError("Sportsbook prices require a source and timezone-aware quote timestamp.")
        try:
            stamp = datetime.fromisoformat(checked.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("odds_checked_at_utc must be a valid timezone-aware timestamp.") from exc
        if stamp.tzinfo is None:
            raise ValueError("odds_checked_at_utc must include a timezone.")
    record = dict(record)
    record["home_team"], record["away_team"] = home, away
    record.update(probs)
    kickoff = str(record.get("kickoff") or "").strip()
    recorded = str(record.get("recorded_at_utc") or "").strip()
    if kickoff:
        if not recorded:
            raise ValueError("A timezone-aware recorded_at_utc is required when kickoff is supplied.")
        try:
            kickoff_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            recorded_dt = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("kickoff and recorded_at_utc must be valid timezone-aware timestamps.") from exc
        if kickoff_dt.tzinfo is None or recorded_dt.tzinfo is None:
            raise ValueError("kickoff and recorded_at_utc must include timezones.")
        if recorded_dt >= kickoff_dt:
            raise ValueError("Forecast must be recorded before scheduled kickoff.")
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
        if row.get("settled_at_utc") or not row.get("season"):
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


def _market_probability_metrics(probabilities, outcomes):
    if not probabilities:
        return {"sample_size": 0, "brier_score": None, "log_loss": None,
                "expected_calibration_error": None, "bins": []}
    clipped = [min(1 - 1e-9, max(1e-9, p)) for p in probabilities]
    brier = sum((p-y)**2 for p, y in zip(probabilities, outcomes)) / len(outcomes)
    log_loss = -sum(y*math.log(p) + (1-y)*math.log(1-p)
                    for p, y in zip(clipped, outcomes)) / len(outcomes)
    bins, ece = [], 0.0
    for low in range(0, 100, 10):
        members = [(p, y) for p, y in zip(probabilities, outcomes)
                   if low/100 <= p < (low+10)/100 or (low == 90 and p == 1.0)]
        if not members:
            continue
        predicted = sum(p for p, _ in members) / len(members)
        observed = sum(y for _, y in members) / len(members)
        ece += len(members) / len(probabilities) * abs(predicted-observed)
        bins.append({"range": f"{low}-{low+10}%", "count": len(members),
                     "mean_probability": round(predicted, 4),
                     "observed_rate": round(observed, 4)})
    return {"sample_size": len(probabilities), "brier_score": round(brier, 6),
            "log_loss": round(log_loss, 6), "expected_calibration_error": round(ece, 6),
            "bins": bins}


def calibration_summary(path="nfl_forecast_ledger.csv"):
    target = Path(path)
    if not target.exists():
        return {"settled_games": 0, "status": "NO_LEDGER", "calibrated": False}
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    settled = [r for r in rows if r.get("settled_at_utc")
               and r.get("actual_home_score") not in ("", None)
               and r.get("actual_away_score") not in ("", None)]
    if not settled:
        return {"settled_games": 0, "status": "NO_SETTLED_GAMES", "calibrated": False}
    ml_p, ml_y, spread_p, spread_y, total_p, total_y = [], [], [], [], [], []
    for row in settled:
        home, away = float(row["actual_home_score"]), float(row["actual_away_score"])
        if row.get("home_win_probability") not in ("", None) and home != away:
            ml_p.append(float(row["home_win_probability"])/100)
            ml_y.append(1 if home > away else 0)
        if row.get("home_spread") not in ("", None) and row.get("home_cover_probability") not in ("", None):
            cover_margin = home - away + float(row["home_spread"])
            if cover_margin != 0:
                spread_p.append(float(row["home_cover_probability"])/100)
                spread_y.append(1 if cover_margin > 0 else 0)
        if row.get("total_line") not in ("", None) and row.get("over_probability") not in ("", None):
            line = float(row["total_line"])
            if home + away != line:
                total_p.append(float(row["over_probability"])/100)
                total_y.append(1 if home + away > line else 0)
    markets = {
        "moneyline_home": _market_probability_metrics(ml_p, ml_y),
        "spread_home": _market_probability_metrics(spread_p, spread_y),
        "total_over": _market_probability_metrics(total_p, total_y),
    }
    return {
        "settled_games": len(settled),
        "home_win_brier_score": markets["moneyline_home"]["brier_score"],
        "spread_brier_score": markets["spread_home"]["brier_score"],
        "total_brier_score": markets["total_over"]["brier_score"],
        "spread_sample_size": markets["spread_home"]["sample_size"],
        "total_sample_size": markets["total_over"]["sample_size"],
        "markets": markets,
        "status": "INSUFFICIENT_SAMPLE" if len(settled) < 100 else "REVIEW_REQUIRED",
        "calibrated": False,
        "note": "Market-specific descriptive metrics only; require chronological holdout, market comparison, sufficient samples and manual review before betting approval.",
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
