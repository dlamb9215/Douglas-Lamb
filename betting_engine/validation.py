"""Chronological, market-specific validation for all four betting models.

This module reports holdout quality; it never turns calibration_ready on.
Predictions must be timestamped before the event and uniquely identified.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math

SPORTS = {"NFL", "NBA", "MLB", "NHL"}


def _timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _metrics(rows: list[dict]) -> dict:
    n = len(rows)
    brier = sum((r["probability"] - r["outcome"]) ** 2 for r in rows) / n
    eps = 1e-15
    log_loss = -sum(
        r["outcome"] * math.log(max(eps, r["probability"]))
        + (1-r["outcome"]) * math.log(max(eps, 1-r["probability"]))
        for r in rows
    ) / n
    bins = []
    for lower in range(0, 100, 10):
        group = [r for r in rows if lower / 100 <= r["probability"] < (lower + 10) / 100]
        if group:
            bins.append({
                "range": f"{lower}-{lower+10}%",
                "count": len(group),
                "mean_probability": round(sum(x["probability"] for x in group) / len(group), 4),
                "observed_rate": round(sum(x["outcome"] for x in group) / len(group), 4),
            })
    return {"sample_size": n, "brier_score": round(brier, 6),
            "log_loss": round(log_loss, 6), "calibration_bins": bins}


def evaluate_chronological_holdout(rows: list[dict], *, min_holdout_rows: int = 200,
                                   train_fraction: float = 0.70) -> dict:
    if not isinstance(rows, list) or not rows:
        raise ValueError("A non-empty pregame prediction ledger is required")
    if not isinstance(min_holdout_rows, int) or min_holdout_rows < 1:
        raise ValueError("min_holdout_rows must be a positive integer")
    if not 0.5 <= train_fraction < 1:
        raise ValueError("train_fraction must be in [0.5, 1)")
    ids = set()
    groups = defaultdict(list)
    for index, source in enumerate(rows, 1):
        required = ("prediction_id", "sport", "market", "forecasted_at",
                    "event_start", "probability", "outcome")
        if any(source.get(key) in (None, "") for key in required):
            raise ValueError(f"Row {index} is missing a required validation field")
        pid = str(source["prediction_id"])
        if pid in ids:
            raise ValueError(f"Duplicate prediction_id: {pid}")
        ids.add(pid)
        sport = str(source["sport"]).upper()
        if sport not in SPORTS:
            raise ValueError(f"Unsupported sport on row {index}: {sport}")
        market = str(source["market"]).strip().lower()
        if not market:
            raise ValueError(f"Market is empty on row {index}")
        forecasted = _timestamp(source["forecasted_at"], "forecasted_at")
        start = _timestamp(source["event_start"], "event_start")
        if forecasted >= start:
            raise ValueError(f"Row {index} is not a pregame forecast")
        p, y = source["probability"], source["outcome"]
        if (isinstance(p, bool) or not isinstance(p, (int, float))
                or not math.isfinite(float(p)) or not 0 <= p <= 1):
            raise ValueError(f"Row {index} probability must be within 0..1")
        if y not in (0, 1, False, True):
            raise ValueError(f"Row {index} outcome must be 0 or 1")
        groups[(sport, market)].append({
            "prediction_id": pid, "forecasted_at": forecasted,
            "probability": float(p), "outcome": int(y),
        })

    reports = []
    for (sport, market), items in sorted(groups.items()):
        items.sort(key=lambda r: r["forecasted_at"])
        split = max(1, min(len(items)-1, int(len(items) * train_fraction))) if len(items) > 1 else len(items)
        train, holdout = items[:split], items[split:]
        report = {
            "sport": sport, "market": market,
            "train_rows": len(train), "holdout_rows": len(holdout),
            "holdout_status": "ELIGIBLE_FOR_MANUAL_REVIEW" if len(holdout) >= min_holdout_rows else "INSUFFICIENT_HOLDOUT_SAMPLE",
            "calibration_ready": False,
            "note": "Holdout metrics are descriptive only; review market baseline, CLV, ROI uncertainty, data leakage and model version before approval.",
        }
        if holdout:
            report.update(_metrics(holdout))
        else:
            report.update({"sample_size": 0, "brier_score": None, "log_loss": None, "calibration_bins": []})
        reports.append(report)
    return {
        "sports": sorted({sport for sport, _ in groups}),
        "markets_evaluated": len(reports),
        "reports": reports,
        "calibration_ready": False,
        "release_status": "REVIEW_REQUIRED",
    }
