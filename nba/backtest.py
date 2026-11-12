"""Evaluate NBA forecasts against settled scores and closing markets.

Accepts the versioned prediction ledger and legacy CSV input. Pending rows and
forecasts recorded at/after scheduled tip are excluded. Calibration remains
closed until chronological out-of-sample review is completed.
"""
import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path


def mean(values):
    return sum(values) / len(values) if values else None


def calibration(rows, key, outcome):
    bins = []
    for low in range(0, 100, 10):
        group = [r for r in rows if r.get(key) is not None and low <= r[key] < low + 10]
        if group:
            bins.append({
                "range": f"{low}-{low+10}%", "count": len(group),
                "mean_probability": mean([r[key] for r in group]),
                "observed_rate": mean([r[outcome] for r in group]) * 100,
            })
    return bins


def _float(row, key):
    value = row.get(key, "")
    return float(value) if str(value).strip() else None


def evaluate(path):
    with open(path, newline="", encoding="utf-8") as handle:
        raw = list(csv.DictReader(handle))
    if not raw:
        raise ValueError("No archived game rows found")

    for row in raw:
        if not row.get("spread") and row.get("spread_line"):
            row["spread"] = row["spread_line"]
        if not row.get("total") and row.get("total_line"):
            row["total"] = row["total_line"]

    settled = [row for row in raw if str(row.get("actual_home", "")).strip()
               and str(row.get("actual_away", "")).strip()]
    pending = len(raw) - len(settled)
    if not settled:
        raise ValueError("No settled forecast rows found; settle completed games before backtesting")

    ids = [row.get("forecast_id") for row in settled if row.get("forecast_id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate forecast_id values found; refusing a contaminated backtest")

    rows = []
    postgame_excluded = 0
    for index, source in enumerate(settled, 2):
        try:
            ph, pa = float(source["projected_home"]), float(source["projected_away"])
            ah, aa = float(source["actual_home"]), float(source["actual_away"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid required prediction/score values on CSV row {index}: {exc}") from exc

        forecasted_at = source.get("forecasted_at", "")
        game_start = source.get("game_start_time", "")
        if forecasted_at and game_start:
            try:
                forecast_time = datetime.fromisoformat(forecasted_at.replace("Z", "+00:00"))
                start_time = datetime.fromisoformat(game_start.replace("Z", "+00:00"))
                if forecast_time.tzinfo is None or start_time.tzinfo is None:
                    raise ValueError("forecast and game start timestamps must include timezones")
                if forecast_time >= start_time:
                    postgame_excluded += 1
                    continue
            except ValueError as exc:
                raise ValueError(f"Invalid forecast timing on CSV row {index}: {exc}") from exc

        item = {
            "projected_home": ph, "projected_away": pa, "actual_home": ah, "actual_away": aa,
            "predicted_total": ph + pa, "actual_total": ah + aa,
            "predicted_margin": ph - pa, "actual_margin": ah - aa,
        }
        for key in ("home_win_probability", "spread", "total", "home_cover_probability",
                    "over_probability", "closing_spread", "closing_total"):
            try:
                item[key] = _float(source, key)
            except ValueError as exc:
                raise ValueError(f"Invalid {key} on CSV row {index}") from exc

        for key in ("home_win_probability", "home_cover_probability", "over_probability"):
            probability = item.get(key)
            if probability is not None and not 0 <= probability <= 100:
                raise ValueError(f"{key} outside 0-100 on CSV row {index}")

        item["home_win"] = (1 if ah > aa else 0) if ah != aa else None
        if item["spread"] is not None:
            value = item["actual_margin"] + item["spread"]
            item["home_cover"] = 1 if value > 0 else 0 if value < 0 else None
        if item["total"] is not None:
            value = item["actual_total"] - item["total"]
            item["over"] = 1 if value > 0 else 0 if value < 0 else None
        rows.append(item)

    if not rows:
        raise ValueError("No valid pregame settled forecasts remain after timestamp checks")

    result = {
        "games": len(rows), "pending_rows_excluded": pending,
        "postgame_forecasts_excluded": postgame_excluded,
        "home_points_mae": mean([abs(x["projected_home"] - x["actual_home"]) for x in rows]),
        "away_points_mae": mean([abs(x["projected_away"] - x["actual_away"]) for x in rows]),
        "total_points_mae": mean([abs(x["predicted_total"] - x["actual_total"]) for x in rows]),
        "margin_mae": mean([abs(x["predicted_margin"] - x["actual_margin"]) for x in rows]),
        "total_bias": mean([x["predicted_total"] - x["actual_total"] for x in rows]),
        "moneyline_games": sum(x.get("home_win") is not None for x in rows),
        "spread_games": sum(x.get("home_cover") is not None for x in rows),
        "total_games": sum(x.get("over") is not None for x in rows),
    }

    for key, outcome, name in (
        ("home_win_probability", "home_win", "moneyline"),
        ("home_cover_probability", "home_cover", "spread"),
        ("over_probability", "over", "total"),
    ):
        eligible = [x for x in rows if x.get(key) is not None and x.get(outcome) is not None]
        if eligible:
            probs = [x[key] / 100 for x in eligible]
            actual = [x[outcome] for x in eligible]
            clipped = [min(.999999, max(.000001, p)) for p in probs]
            result[name + "_brier"] = mean([(p-y)**2 for p, y in zip(probs, actual)])
            result[name + "_log_loss"] = mean([
                -(y*math.log(p) + (1-y)*math.log(1-p)) for p, y in zip(clipped, actual)
            ])
            result[name + "_calibration"] = calibration(eligible, key, outcome)
            result[name + "_hit_rate"] = mean(actual) * 100

    market_counts = {
        "moneyline": sum(x.get("home_win") is not None and x.get("home_win_probability") is not None for x in rows),
        "spread": sum(x.get("home_cover") is not None and x.get("home_cover_probability") is not None for x in rows),
        "total": sum(x.get("over") is not None and x.get("over_probability") is not None for x in rows),
    }
    result["calibration_sample_counts"] = market_counts
    result["calibration_sample_gate"] = {
        market: {"required": 200, "observed": count, "sample_sufficient": count >= 200}
        for market, count in market_counts.items()
    }
    result["calibration_ready"] = False
    result["calibration_note"] = (
        "Sample counts alone cannot authorize betting. Require chronological holdout, "
        "positive CLV, acceptable Brier/log-loss versus market baseline, and manual review."
    )

    spread_clv = [x["closing_spread"] - x["spread"] for x in rows
                  if x.get("closing_spread") is not None and x.get("spread") is not None]
    total_clv = [x["closing_total"] - x["total"] for x in rows
                 if x.get("closing_total") is not None and x.get("total") is not None]
    if spread_clv:
        result["mean_closing_spread_minus_opening_spread"] = mean(spread_clv)
    if total_clv:
        result["mean_closing_total_minus_opening_total"] = mean(total_clv)
    return result


def main():
    parser = argparse.ArgumentParser(description="Backtest archived Doug's Elite NBA Simulator predictions")
    parser.add_argument("--csv", default="nba/ledger/predictions.csv")
    parser.add_argument("--output", default="nba-backtest-report.json")
    args = parser.parse_args()
    report = evaluate(args.csv)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
