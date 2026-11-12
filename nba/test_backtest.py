import csv
import tempfile
import unittest
from pathlib import Path

from nba.backtest import evaluate


class TestBacktest(unittest.TestCase):
    def test_rejects_invalid_probability(self):
        rows = [{
            "projected_home": 110, "projected_away": 105,
            "actual_home": 112, "actual_away": 104,
            "home_win_probability": 120,
        }]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                evaluate(path)

    def test_ledger_backtest_excludes_pending_and_postgame_rows(self):
        rows = [
            {
                "forecast_id": "pre", "projected_home": 110, "projected_away": 105,
                "actual_home": 112, "actual_away": 104, "home_win_probability": 65,
                "forecasted_at": "2026-11-12T18:00:00Z", "game_start_time": "2026-11-12T23:00:00Z",
                "spread_line": -3.5, "total_line": 215.5, "home_cover_probability": 60,
                "over_probability": 55,
            },
            {
                "forecast_id": "post", "projected_home": 100, "projected_away": 105,
                "actual_home": 98, "actual_away": 104, "home_win_probability": 40,
                "forecasted_at": "2026-11-12T23:30:00Z", "game_start_time": "2026-11-12T23:00:00Z",
            },
            {
                "forecast_id": "pending", "projected_home": 100, "projected_away": 105,
                "actual_home": "", "actual_away": "", "home_win_probability": 40,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            result = evaluate(path)
        self.assertEqual(result["games"], 1)
        self.assertEqual(result["pending_rows_excluded"], 1)
        self.assertEqual(result["postgame_forecasts_excluded"], 1)
        self.assertFalse(result["calibration_ready"])

    def test_rejects_duplicate_forecast_ids(self):
        row = {
            "forecast_id": "same", "projected_home": 110, "projected_away": 105,
            "actual_home": 112, "actual_away": 104,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=row.keys())
                writer.writeheader()
                writer.writerow(row)
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "Duplicate forecast_id"):
                evaluate(path)

    def test_metrics_on_small_fixture(self):
        rows = [
            {
                "projected_home": 110,
                "projected_away": 105,
                "actual_home": 112,
                "actual_away": 104,
                "spread": -3.5,
                "total": 215.5,
                "home_cover_probability": 60,
                "over_probability": 55,
                "home_win_probability": 65,
            },
            {
                "projected_home": 100,
                "projected_away": 108,
                "actual_home": 98,
                "actual_away": 110,
                "spread": 2.5,
                "total": 210.5,
                "home_cover_probability": 45,
                "over_probability": 48,
                "home_win_probability": 40,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            result = evaluate(path)

        self.assertEqual(result["games"], 2)
        self.assertEqual(result["moneyline_games"], 2)
        self.assertGreaterEqual(result["total_points_mae"], 0)
        self.assertIn("moneyline_brier", result)
        self.assertIn("spread_brier", result)
        self.assertIn("total_calibration", result)


if __name__ == "__main__":
    unittest.main()
