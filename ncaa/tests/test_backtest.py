import unittest
from ncaa.backtest import evaluate_predictions


class BacktestTests(unittest.TestCase):
    def test_brier_accuracy_and_calibration_are_reported(self):
        result = evaluate_predictions([
            {"home_win_probability": "0.8", "home_win": "1",
             "home_cover_probability": "0.6", "home_cover": "1",
             "over_probability": "0.4", "over": "0"},
            {"home_win_probability": "0.3", "home_win": "0",
             "home_cover_probability": "0.4", "home_cover": "0",
             "over_probability": "0.7", "over": "1"},
        ])
        self.assertEqual(result["moneyline"]["sample_size"], 2)
        self.assertEqual(result["moneyline"]["accuracy"], 1.0)
        self.assertIsNotNone(result["spread"])
        self.assertIsNotNone(result["total"])

    def test_only_pregame_rows_are_used_when_status_is_present(self):
        result = evaluate_predictions([
            {"pregame_status": "pregame", "home_win_probability": "0.8", "home_win": "1"},
            {"pregame_status": "postgame", "home_win_probability": "0.1", "home_win": "0"},
            {"pregame_status": "unknown", "home_win_probability": "0.9", "home_win": "1"},
        ])
        self.assertEqual(result["games"], 1)
        self.assertEqual(result["excluded_non_pregame_or_unknown"], 2)
        self.assertEqual(result["moneyline"]["sample_size"], 1)

    def test_invalid_probability_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_predictions([{"home_win_probability": "1.2", "home_win": "1"}])

    def test_missing_optional_markets_are_allowed(self):
        result = evaluate_predictions([{"home_win_probability": "0.6", "home_win": "1"}])
        self.assertIsNone(result["spread"])
        self.assertIsNone(result["total"])


if __name__ == "__main__":
    unittest.main()
