"""Out-of-sample evaluation for archived NBA player-prop projections.

CSV columns: player, stat, projection, actual, line, over_probability.
Optional: closing_line. Probabilities are percentages (0-100).
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def mean(values):
    return sum(values) / len(values) if values else None


def evaluate(path):
    groups = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        required = {"player", "stat", "projection", "actual", "line", "over_probability"}
        if not required.issubset(set(rows.fieldnames or [])):
            raise ValueError("CSV must include: " + ", ".join(sorted(required)))
        for row_number, row in enumerate(rows, 2):
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
    report = {"total_rows": sum(map(len, groups.values())), "by_stat": {}}
    for stat, items in sorted(groups.items()):
        probs = [min(.999999, max(.000001, x["probability"])) for x in items]
        outcomes = [x["over"] for x in items]
        report["by_stat"][stat] = {
            "bets": len(items),
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
