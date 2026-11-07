import csv
import tempfile
import unittest
from pathlib import Path
from nfl_forecast_ledger import append_forecast, reconcile_results, calibration_summary


class NFLForecastLedgerTests(unittest.TestCase):
    def test_append_deduplicates_run_and_reconciles_final_score(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            record = {
                "run_id":"run-1","season":2026,"week":9,"home_team":"BUF","away_team":"MIA",
                "home_win_probability":62.0,"away_win_probability":38.0,
                "home_spread":-3.5,"home_cover_probability":55.0,
                "total_line":48.5,"over_probability":51.0
            }
            self.assertTrue(append_forecast(record,path))
            self.assertFalse(append_forecast(record,path))
            result = reconcile_results([{
                "game_type":"REG","season":"2026","week":"9",
                "home_team":"BUF","away_team":"MIA","home_score":"27","away_score":"20"
            }],path)
            self.assertEqual(result["settled"],1)
            summary=calibration_summary(path)
            self.assertEqual(summary["settled_games"],1)
            self.assertEqual(summary["home_win_brier_score"],0.1444)
            self.assertFalse(summary["calibrated"])
            self.assertEqual(summary["spread_sample_size"], 1)
            self.assertEqual(summary["total_sample_size"], 1)
            self.assertEqual(summary["spread_brier_score"], 0.2025)
            self.assertEqual(summary["total_brier_score"], 0.2601)

    def test_rejects_invalid_probabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                append_forecast({"run_id":"x","home_team":"BUF","away_team":"MIA",
                                 "home_win_probability":101,"away_win_probability":0},
                                Path(directory)/"ledger.csv")


if __name__ == "__main__":
    unittest.main()
