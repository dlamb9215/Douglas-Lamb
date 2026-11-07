"""Evaluate historical probability calibration from a settled prediction ledger.

Rows require probability (0..1) and outcome (0 or 1). This module reports
metrics; it never declares a model calibrated from a small or in-sample set.
"""
import json
import math
from pathlib import Path


def evaluate_predictions(rows, min_rows=100):
    if not isinstance(rows, list) or not rows:
        raise ValueError("A non-empty prediction ledger is required.")
    probabilities, outcomes = [], []
    for index, row in enumerate(rows):
        p, y = row.get("probability"), row.get("outcome")
        if (not isinstance(p, (int, float)) or isinstance(p, bool)
                or not math.isfinite(p) or not 0 <= p <= 1):
            raise ValueError(f"Row {index + 1}: probability must be within 0..1.")
        if y not in (0, 1, False, True):
            raise ValueError(f"Row {index + 1}: outcome must be 0 or 1.")
        probabilities.append(float(p))
        outcomes.append(int(y))
    n = len(rows)
    brier = sum((p-y)**2 for p, y in zip(probabilities, outcomes)) / n
    eps = 1e-15
    log_loss = -sum(
        y * math.log(max(eps, p)) + (1-y) * math.log(max(eps, 1-p))
        for p, y in zip(probabilities, outcomes)
    ) / n
    bins = []
    for lower in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        members = [(p, y) for p, y in zip(probabilities, outcomes)
                   if lower <= p < lower + 0.1 or (lower == 0.9 and p == 1.0)]
        if members:
            bins.append({
                "range": f"{lower:.1f}-{lower+0.1:.1f}",
                "count": len(members),
                "mean_probability": round(sum(p for p, _ in members)/len(members), 4),
                "observed_rate": round(sum(y for _, y in members)/len(members), 4),
            })
    return {
        "sample_size": n,
        "minimum_sample_for_review": min_rows,
        "brier_score": round(brier, 6),
        "log_loss": round(log_loss, 6),
        "calibration_bins": bins,
        "review_status": "ELIGIBLE_FOR_CALIBRATION_REVIEW" if n >= min_rows else "INSUFFICIENT_SAMPLE",
        "calibrated": False,
        "note": "Use time-ordered out-of-sample predictions and separate markets before setting betting thresholds.",
    }


def evaluate_file(path):
    return evaluate_predictions(json.loads(Path(path).read_text(encoding="utf-8")))
