"""Evaluate saved NCAA pregame predictions against final results.

Input CSV requires home_win_probability and home_win (0/1). Optional paired
columns: home_cover_probability/home_cover and over_probability/over.
Predictions must be recorded before kickoff; do not backfill forecasts.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def _binary(value: str, field: str) -> int:
    parsed = int(value)
    if parsed not in (0, 1):
        raise ValueError(f"{field} must be 0 or 1")
    return parsed


def _probability(value: str, field: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0 <= parsed <= 1:
        raise ValueError(f"{field} must be between 0 and 1")
    return parsed


def _score(rows: list[dict], probability_field: str, outcome_field: str) -> dict | None:
    pairs = []
    for row in rows:
        probability = (row.get(probability_field) or "").strip()
        outcome = (row.get(outcome_field) or "").strip()
        if not probability or not outcome:
            continue
        pairs.append((_probability(probability, probability_field),
                      _binary(outcome, outcome_field)))
    if not pairs:
        return None
    brier = sum((p - y) ** 2 for p, y in pairs) / len(pairs)
    log_loss = -sum(
        y * math.log(min(max(p, 1e-15), 1 - 1e-15)) +
        (1 - y) * math.log(1 - min(max(p, 1e-15), 1 - 1e-15))
        for p, y in pairs
    ) / len(pairs)
    accuracy = sum((p >= 0.5) == bool(y) for p, y in pairs) / len(pairs)
    bins = []
    for index in range(10):
        bucket = [(p, y) for p, y in pairs
                  if index / 10 <= p < (index + 1) / 10
                  or (index == 9 and p == 1)]
        if bucket:
            bins.append({
                "range": f"{index / 10:.1f}-{(index + 1) / 10:.1f}",
                "count": len(bucket),
                "mean_predicted": round(sum(p for p, _ in bucket) / len(bucket), 4),
                "observed_rate": round(sum(y for _, y in bucket) / len(bucket), 4),
            })
    return {
        "sample_size": len(pairs),
        "brier_score": round(brier, 5),
        "log_loss": round(log_loss, 5),
        "accuracy": round(accuracy, 5),
        "calibration_bins": bins,
    }


def evaluate_predictions(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("No prediction rows found")
    return {
        "games": len(rows),
        "moneyline": _score(rows, "home_win_probability", "home_win"),
        "spread": _score(rows, "home_cover_probability", "home_cover"),
        "total": _score(rows, "over_probability", "over"),
        "warning": "Evaluation is meaningful only for timestamped predictions saved before kickoff.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest NCAA simulator forecasts")
    parser.add_argument("--input", required=True, help="CSV of pregame forecasts and actual outcomes")
    parser.add_argument("--output", default="ncaa-backtest-results.json")
    args = parser.parse_args()
    with Path(args.input).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = evaluate_predictions(rows)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Backtest report saved to {args.output}")


if __name__ == "__main__":
    main()
