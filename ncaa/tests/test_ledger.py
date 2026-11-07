import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ncaa.forecast_ledger import append_forecast, FIELDS
from ncaa.reconcile import reconcile_ledger


class ForecastLedgerTests(unittest.TestCase):
    def make_result(self):
        return {
            "season": "2026", "home_team": "Home U", "away_team": "Away U",
            "trials": 100000, "seed": 123,
            "home_win_probability": 0.62,
            "market": {"home_spread": -3.5, "home_cover_probability": 0.54,
                       "total_line": 42.5, "over_probability": 0.51},
            "sportsbook_analysis": {},
            "market_prices": {},
            "profiles": {"Home U": {"as_of": "2026-11-07"},
                         "Away U": {"as_of": "2026-11-07"}},
            "data_quality": {"warnings": []},
        }

    def test_append_records_pregame_and_prevents_duplicate_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            now = datetime.now(timezone.utc)
            kickoff = (now + timedelta(days=1)).isoformat()
            first = append_forecast(self.make_result(), path, kickoff, "run-1", now)
            second = append_forecast(self.make_result(), path, kickoff, "run-1", now)
            self.assertTrue(first["appended"])
            self.assertEqual(first["pregame_status"], "pregame")
            self.assertFalse(second["appended"])
            with path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["home_team"], "Home U")
            self.assertEqual(rows[0]["home_cover_probability"], "0.54")

    def test_reconcile_fills_final_results_from_cfbd(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            now = datetime.now(timezone.utc)
            kickoff = (now + timedelta(hours=2)).isoformat()
            append_forecast(self.make_result(), path, kickoff, "run-2", now)
            game = {
                "homeTeam": "Home U", "awayTeam": "Away U",
                "startDate": kickoff, "homePoints": 24, "awayPoints": 20,
            }
            with patch("ncaa.reconcile.api_get", return_value=[game]):
                status = reconcile_ledger(path, 2026, "test-key")
            self.assertEqual(status["updated"], 1)
            with path.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["home_win"], "1")
            self.assertEqual(row["home_cover"], "1")
            self.assertEqual(row["over"], "1")
            self.assertEqual(row["outcome_source"], "CollegeFootballData games API")

    def test_kickoff_requires_timezone(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "timezone"):
                append_forecast(self.make_result(), Path(directory) / "ledger.csv",
                                "2026-11-08T12:00:00", "run-3")


if __name__ == "__main__":
    unittest.main()
