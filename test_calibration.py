import unittest
from calibration import evaluate_predictions


class CalibrationTests(unittest.TestCase):
    def test_metrics_and_sample_warning(self):
        result = evaluate_predictions([
            {"probability": 0.8, "outcome": 1},
            {"probability": 0.2, "outcome": 0},
        ], min_rows=100)
        self.assertEqual(result["sample_size"], 2)
        self.assertEqual(result["brier_score"], 0.04)
        self.assertEqual(result["review_status"], "INSUFFICIENT_SAMPLE")
        self.assertFalse(result["calibrated"])

    def test_invalid_probability_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_predictions([{"probability": 1.2, "outcome": 1}])


if __name__ == "__main__":
    unittest.main()
