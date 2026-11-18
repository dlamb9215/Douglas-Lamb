import unittest
from datetime import datetime, timezone, timedelta

from betting_engine.validation import evaluate_chronological_holdout


class ChronologicalValidationTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.rows = []
        for i in range(20):
            forecast = start + timedelta(days=i)
            event = forecast + timedelta(hours=4)
            self.rows.append({
                "prediction_id": f"nba-moneyline-{i}",
                "sport": "NBA", "market": "moneyline",
                "forecasted_at": forecast.isoformat(),
                "event_start": event.isoformat(),
                "probability": 0.6 if i % 2 else 0.4,
                "outcome": 1 if i % 2 else 0,
            })

    def test_splits_chronologically_and_never_self_approves(self):
        result = evaluate_chronological_holdout(self.rows, min_holdout_rows=5)
        row = result["reports"][0]
        self.assertEqual(row["train_rows"], 14)
        self.assertEqual(row["holdout_rows"], 6)
        self.assertFalse(row["calibration_ready"])
        self.assertFalse(result["calibration_ready"])
        self.assertEqual(row["brier_score"], 0.16)

    def test_holdout_splits_by_event_start_not_forecast_creation_time(self):
        rows = [dict(row) for row in self.rows]
        rows[0]["forecasted_at"] = (datetime(2026, 1, 29, tzinfo=timezone.utc)).isoformat()
        rows[0]["event_start"] = (datetime(2026, 1, 30, tzinfo=timezone.utc)).isoformat()
        rows[-1]["forecasted_at"] = (datetime(2026, 1, 1, tzinfo=timezone.utc)).isoformat()
        rows[-1]["event_start"] = (datetime(2026, 1, 2, tzinfo=timezone.utc)).isoformat()
        result = evaluate_chronological_holdout(rows, min_holdout_rows=5)
        report = result["reports"][0]
        self.assertLessEqual(report["train_event_end"], report["holdout_event_start"])

    def test_postgame_prediction_rejected(self):
        self.rows[0]["event_start"] = self.rows[0]["forecasted_at"]
        with self.assertRaises(ValueError):
            evaluate_chronological_holdout(self.rows)

    def test_duplicate_prediction_rejected(self):
        self.rows[1]["prediction_id"] = self.rows[0]["prediction_id"]
        with self.assertRaises(ValueError):
            evaluate_chronological_holdout(self.rows)

    def test_market_specific_groups_are_separate(self):
        other = dict(self.rows[0])
        other.update({"prediction_id": "nhl-props", "sport": "NHL", "market": "shots"})
        result = evaluate_chronological_holdout(self.rows + [other])
        self.assertEqual(result["markets_evaluated"], 2)


if __name__ == "__main__":
    unittest.main()
