"""Out-of-sample evaluation for archived NBA player-prop projections.

CSV columns: player, stat, projection, actual, line, over_probability.
Optional: closing_line. Probabilities are percentages (0-100).
"""
import argparse
import csv
import json
import math
from datetime import datetime
from collections import defaultdict
from pathlib import Path


def mean(values):
    return sum(values) / len(values) if values else None


def evaluate(path):
    groups = defaultdict(list)
    forecast_ids = set()
    postgame_excluded = 0
    with open(path, newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        required = {"player", "stat", "projection", "actual", "line", "over_probability"}
        if not required.issubset(set(rows.fieldnames or [])):
            raise ValueError("CSV must include: " + ", ".join(sorted(required)))
        for row_number, row in enumerate(rows, 2):
            forecast_id = (row.get("forecast_id") or "").strip()
            if forecast_id:
                if forecast_id in forecast_ids:
                    raise ValueError(f"Duplicate forecast_id on CSV row {row_number}: {forecast_id}")
                forecast_ids.add(forecast_id)
            forecasted_at = (row.get("forecasted_at") or "").strip()
            game_start_time = (row.get("game_start_time") or "").strip()
            if bool(forecasted_at) != bool(game_start_time):
                raise ValueError(f"CSV row {row_number}: forecasted_at and game_start_time must be supplied together.")
            if forecasted_at and game_start_time:
                try:
                    forecast_time = datetime.fromisoformat(forecasted_at.replace("Z", "+00:00"))
                    start_time = datetime.fromisoformat(game_start_time.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"Invalid forecast timing on CSV row {row_number}: {exc}") from exc
                if forecast_time.tzinfo is None or start_time.tzinfo is None:
                    raise ValueError(f"CSV row {row_number}: forecast timestamps must include timezones.")
                if forecast_time >= start_time:
                    postgame_excluded += 1
                    continue
            try:
                stat = row["stat"].strip().lower()
                projection = float(row["projection"])
                actual = float(row["actual"])
                line = float(row["line"])
                probability = float(row["over_probability"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid values on CSV row {row_number}: {exc}") from exc
            if stat not in {"points", "rebounds", "assists", "pra"}:
                raise ValueError(f"Unsupported stat on CSV row {row_number}: {stat}")
            if not 0 <= probability <= 100:
                raise ValueError(f"Probability outside 0-100 on CSV row {row_number}")
            if actual == line:
                continue  # pushes are excluded from binary over/under calibration
            item = {"player": row["player"], "projection": projection, "actual": actual,
                    "line": line, "probability": probability / 100,
                    "over": 1 if actual > line else 0}
            groups[stat].append(item)
    if not groups:
        raise ValueError("No non-push player prop rows found")
    report = {"total_rows": sum(map(len, groups.values())), "postgame_rows_excluded": postgame_excluded,
              "by_stat": {}, "calibration_ready": False,
              "calibration_note": "Sample counts alone do not authorize betting; require chronological holdout, market comparison and manual review."}
    for stat, items in sorted(groups.items()):
        probs = [min(.999999, max(.000001, x["probability"])) for x in items]
        outcomes = [x["over"] for x in items]
        report["by_stat"][stat] = {
            "bets": len(items),
            "minimum_sample_for_review": 200,
            "sample_sufficient_for_review": len(items) >= 200,
            "projection_mae": mean([abs(x["projection"] - x["actual"]) for x in items]),
            "over_brier": mean([(p-y)**2 for p, y in zip(probs, outcomes)]),
            "over_log_loss": mean([-(y*math.log(p)+(1-y)*math.log(1-p))
                                   for p, y in zip(probs, outcomes)]),
            "over_hit_rate_pct": mean(outcomes) * 100,
            "mean_predicted_over_pct": mean([p for p in probs]) * 100,
            "calibration": [
                {"bucket": f"{low}-{low+10}%", "count": sum(low/100 <= p < (low+10)/100 for p in probs),
                 "predicted_pct": mean([p for p in probs if low/100 <= p < (low+10)/100]) * 100,
                 "observed_pct": mean([y for p, y in zip(probs, outcomes)
                                       if low/100 <= p < (low+10)/100]) * 100}
                for low in range(0, 100, 10)
                if any(low/100 <= p < (low+10)/100 for p in probs)
            ],
        }
    return report


def main():
    parser = argparse.ArgumentParser(description="Backtest NBA player props")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output", default="nba-player-prop-backtest.json")
    args = parser.parse_args()
    result = evaluate(args.csv)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
