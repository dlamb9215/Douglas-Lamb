
import unittest

from main import simulate_game


class TestDougSimulator(unittest.TestCase):

    def test_runs_100000_trials(self):
        result = simulate_game(
            24, 21, 10, 10, -3, 45, 100000
        )
        self.assertIn("home_win", result)
        self.assertIn("away_win", result)
        self.assertIn("over", result)
        self.assertIn("under", result)

    def test_probabilities_are_valid(self):
        result = simulate_game(
            24, 21, 10, 10, -3, 45, 10000
        )

        for key in [
            "home_win",
            "away_win",
            "home_cover",
            "away_cover",
            "over",
            "under"
        ]:
            self.assertGreaterEqual(result[key], 0)
            self.assertLessEqual(result[key], 100)

    def test_projected_scores(self):
        result = simulate_game(
            24, 21, 10, 10, -3, 45, 10000
        )

        self.assertGreater(result["home_avg"], 0)
        self.assertGreater(result["away_avg"], 0)


if __name__ == "__main__":
    unittest.main()
