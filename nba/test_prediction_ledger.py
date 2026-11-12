import csv
import tempfile
import unittest
from pathlib import Path

from nba.prediction_ledger import FIELDS, append_forecast, build_row


def fixture():
    return {
        "home_team": "BOS", "away_team": "NYK", "data_updated_at": "2026-11-12T12:00:00Z",
        "spread_line": -3.5, "total_line": 220.5, "home_ml_odds": -150, "away_ml_odds": 130,
        "home_spread_odds": -110, "away_spread_odds": -110, "over_odds": -108, "under_odds": -112,
        "availability_confirmed": False, "data_ready": True,
        "schedule_context": {"event": {"event_id": "evt-1"}},
        "odds_context": {
            "source": "The Odds API v4", "moneyline_bookmaker": "book-a",
            "spread_bookmaker": "book-b", "total_bookmaker": "book-a",
            "moneyline_last_updated": "2026-11-12T17:00:00Z",
            "spread_last_updated": "2026-11-12T17:01:00Z",
            "total_last_updated": "2026-11-12T17:02:00Z",
        },
        "result": {
            "trials": 1000000, "home_avg": 112.4, "away_avg": 108.1,
            "total_avg": 220.5, "home_win": 61.2, "away_win": 38.8,
            "home_cover": 55.1, "away_cover": 44.9, "over": 50.2, "under": 49.8,
        },
    }


class TestPredictionLedger(unittest.TestCase):
    def test_build_row_preserves_prediction_and_quote_provenance(self):
        row = build_row(fixture(), "123", "abc", "2026-11-12T18:00:00Z")
        self.assertEqual(row["forecast_id"], "123:evt-1:BOS:NYK")
        self.assertAlmostEqual(row["projected_margin"], 4.3)
        self.assertEqual(row["spread_bookmaker"], "book-b")
        self.assertEqual(row["spread_quote_at"], "2026-11-12T17:01:00Z")
        self.assertEqual(row["actual_home"], "")
        self.assertEqual(row["workflow_run_id"], "123")

    def test_append_is_idempotent_and_does_not_overwrite_existing_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = Path(folder) / "payload.json"
            import json
            payload.write_text(json.dumps(fixture()), encoding="utf-8")
            ledger = Path(folder) / "predictions.csv"
            first = append_forecast(str(payload), str(ledger), "123", "abc")
            second = append_forecast(str(payload), str(ledger), "123", "abc")
            self.assertEqual(first["status"], "archived")
            self.assertEqual(second["status"], "duplicate")
            with ledger.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]), len(FIELDS))

    def test_append_accepts_legacy_literal_backslash_n_terminator(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = Path(folder) / "payload.json"
            import json
            payload.write_text(json.dumps(fixture()) + chr(92) + "n", encoding="utf-8")
            ledger = Path(folder) / "predictions.csv"
            result = append_forecast(str(payload), str(ledger), "legacy-123", "abc")
            self.assertEqual(result["status"], "archived")

    def test_rejects_naive_forecast_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            build_row(fixture(), "123", "abc", "2026-11-12T18:00:00")


if __name__ == "__main__":
    unittest.main()
