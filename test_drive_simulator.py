import unittest

from drive_simulator import (
    _game_script_multiplier,
    simulate_drive_game,
)


class TestDriveSimulator(unittest.TestCase):
    def test_seed_makes_results_reproducible(self):
        first = simulate_drive_game(24, 21, -3.5, 45.5, trials=2000, seed=7)
        second = simulate_drive_game(24, 21, -3.5, 45.5, trials=2000, seed=7)
        self.assertEqual(first, second)

    def test_probabilities_and_pushes_are_bounded(self):
        result = simulate_drive_game(24, 21, -3, 45, trials=5000)
        for key in (
            "home_win", "away_win", "tie", "home_cover", "away_cover",
            "spread_push", "over", "under", "total_push",
        ):
            self.assertGreaterEqual(result[key], 0)
            self.assertLessEqual(result[key], 100)

    def test_script_adjustment_changes_with_score(self):
        self.assertLess(_game_script_multiplier(14), 1.0)
        self.assertGreater(_game_script_multiplier(-14), 1.0)
        self.assertEqual(_game_script_multiplier(0), 1.0)

    def test_first_half_flag_and_trial_count(self):
        result = simulate_drive_game(24, 21, -1.5, 22.5, trials=100, first_half=True)
        self.assertTrue(result["first_half"])
        self.assertEqual(result["trials"], 100)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            simulate_drive_game(-1, 21, 0, 40)
        with self.assertRaises(ValueError):
            simulate_drive_game(24, 21, 0, 40, trials=0)


if __name__ == "__main__":
    unittest.main()
