import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from nhl.ledger import append_forecast, reconcile, calibration_summary


def payload():
    return {
        "home": "TOR", "away": "LAK", "season": 20262027, "trials": 100000, "seed": 9,
        "moneyline_pct": {"home": 55.0, "away": 45.0},
        "puck_line_pct": {"home_minus_1_5": 30.0, "away_plus_1_5": 70.0},
        "total_line": 6.0, "total_pct": {"over": 50.0, "under": 40.0, "push": 10.0},
        "sportsbook_prices": {"home_ml": -120, "away_ml": 110, "over": -110, "under": -110},
        "goalies": {"TOR": {"selected": {"id": 1}}, "LAK": {"selected": {"id": 2}}},
        "data_quality": {"team_summary_features": {
            "TOR": {"available": True}, "LAK": {"available": True}
        }},
    }


class NHLForecastLedgerTests(unittest.TestCase):
    def test_append_records_forecast_and_market_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.csv"
            added = append_forecast(payload(), path, "12345", "2026-11-19",
                                    "ESPN BET", "2026-11-19T10:00:00-05:00")
            self.assertTrue(added)
            row = next(csv.DictReader(path.open()))
            self.assertEqual(row["home"], "TOR")
            self.assertEqual(row["home_ml_odds"], "-120")
            self.assertEqual(row["sportsbook_source"], "ESPN BET")
            self.assertTrue(row["team_summary_available"] == "True")
            self.assertEqual(row["settled_at_utc"], "")

    def test_duplicate_run_is_not_appended_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.csv"
            self.assertTrue(append_forecast(payload(), path, "12345", "2026-11-19",
                                             "ESPN BET", "2026-11-19T10:00:00Z"))
            self.assertFalse(append_forecast(payload(), path, "12345", "2026-11-19",
                                              "ESPN BET", "2026-11-19T10:00:00Z"))
            self.assertEqual(sum(1 for _ in path.open()) - 1, 1)

    def test_prices_require_source_and_timezone_aware_quote_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.csv"
            with self.assertRaisesRegex(ValueError, "source and timezone-aware"):
                append_forecast(payload(), path, "1", "2026-11-19")
            with self.assertRaisesRegex(ValueError, "timezone"):
                append_forecast(payload(), path, "1", "2026-11-19", "ESPN BET", "2026-11-19T10:00:00")

    def test_reconcile_uses_final_official_scores_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.csv"
            p = payload()
            p["sportsbook_prices"] = {}
            append_forecast(p, path, "1", "2026-11-17")
            calls = []
            def fetch(day):
                calls.append(day)
                return {"games": [{
                    "gameState": "OFF",
                    "homeTeam": {"abbrev": "TOR", "score": 4},
                    "awayTeam": {"abbrev": "LAK", "score": 2},
                }]}
            self.assertEqual(reconcile(path, fetch, today=date(2026, 11, 18)), 1)
            self.assertEqual(calls, ["2026-11-17"])
            summary = calibration_summary(path)
            self.assertEqual(summary["settled_games"], 1)
            self.assertEqual(summary["calibration_status"], "INSUFFICIENT_SAMPLE")
            self.assertGreaterEqual(summary["home_moneyline_brier"], 0)

    def test_calibration_reports_separate_market_metrics_and_excludes_total_pushes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.csv"
            p = payload()
            p["sportsbook_prices"] = {}
            append_forecast(p, path, "1", "2026-11-17")
            p2 = payload()
            p2["sportsbook_prices"] = {}
            append_forecast(p2, path, "2", "2026-11-17")
            rows = list(csv.DictReader(path.open()))
            rows[0]["actual_home_goals"], rows[0]["actual_away_goals"] = "4", "2"
            rows[1]["actual_home_goals"], rows[1]["actual_away_goals"] = "3", "3"
            for row in rows:
                row["settled_at_utc"] = "2026-11-18T00:00:00+00:00"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            report = calibration_summary(path)
        self.assertEqual(report["markets"]["moneyline_home"]["sample_size"], 1)
        self.assertEqual(report["markets"]["home_puck_line_minus_1_5"]["sample_size"], 2)
        self.assertEqual(report["markets"]["total_over"]["sample_size"], 0)
        self.assertFalse(report["calibrated"])

    def test_live_or_unfinished_game_is_not_settled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.csv"
            p = payload()
            p["sportsbook_prices"] = {}
            append_forecast(p, path, "1", "2026-11-17")
            fetch = lambda day: {"games": [{
                "gameState": "LIVE",
                "homeTeam": {"abbrev": "TOR", "score": 2},
                "awayTeam": {"abbrev": "LAK", "score": 1},
            }]}
            self.assertEqual(reconcile(path, fetch, today=date(2026, 11, 18)), 0)
            self.assertEqual(calibration_summary(path)["settled_games"], 0)


if __name__ == "__main__":
    unittest.main()
