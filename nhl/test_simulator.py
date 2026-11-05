import unittest

from nhl.simulator import (
    adjusted_goal_means,
    current_season_id,
    simulate_matchup,
    validate_matchup,
)


class TestNHLSimulator(unittest.TestCase):
    def setUp(self):
        self.db = {
            "BOS": {
                "name": "Boston Bruins", "games_played": 20,
                "goals_for_per_game": 3.2, "goals_against_per_game": 2.7,
                "shots_for_per_game": 30.0, "shots_against_per_game": 27.0,
                "power_play_pct": 24.0, "penalty_kill_pct": 82.0,
                "faceoff_win_pct": 51.0, "season": 20262027,
            },
            "FLA": {
                "name": "Florida Panthers", "games_played": 20,
                "goals_for_per_game": 3.4, "goals_against_per_game": 2.9,
                "shots_for_per_game": 32.0, "shots_against_per_game": 28.0,
                "power_play_pct": 22.0, "penalty_kill_pct": 80.0,
                "faceoff_win_pct": 52.0, "season": 20262027,
            },
        }

    def test_current_season_rollover(self):
        from datetime import datetime, timezone
        self.assertEqual(current_season_id(datetime(2026, 11, 5, tzinfo=timezone.utc)), 20262027)
        self.assertEqual(current_season_id(datetime(2027, 3, 1, tzinfo=timezone.utc)), 20262027)
        self.assertEqual(current_season_id(datetime(2027, 8, 1, tzinfo=timezone.utc)), 20262027)

    def test_home_ice_and_special_teams_are_applied(self):
        home, away = adjusted_goal_means(self.db, "BOS", "FLA")
        self.assertGreater(home, 0)
        self.assertGreater(away, 0)
        self.assertAlmostEqual(home, 3.2 * 0 + home, places=6)

    def test_simulation_runs_100000_trials(self):
        result = simulate_matchup(self.db, "BOS", "FLA", trials=100000, seed=7)
        self.assertEqual(result["trials"], 100000)
        self.assertAlmostEqual(result["home_win_pct"] + result["away_win_pct"], 100.0)

    def test_reproducible_seed(self):
        first = simulate_matchup(self.db, "BOS", "FLA", trials=5000, seed=99)
        second = simulate_matchup(self.db, "BOS", "FLA", trials=5000, seed=99)
        self.assertEqual(first, second)

    def test_invalid_matchups_rejected(self):
        with self.assertRaises(ValueError):
            validate_matchup(self.db, "BOS", "BOS")
        with self.assertRaises(ValueError):
            validate_matchup(self.db, "BOS", "XXX")

    def test_bad_trial_count_rejected(self):
        with self.assertRaises(ValueError):
            simulate_matchup(self.db, "BOS", "FLA", trials=0)

    def test_simulated_probabilities_stay_in_range(self):
        result = simulate_matchup(self.db, "BOS", "FLA", trials=10000)
        for key in ("home_win_pct", "away_win_pct", "over_pct", "under_pct", "home_puck_line_pct", "away_puck_line_pct"):
            self.assertGreaterEqual(result[key], 0)
            self.assertLessEqual(result[key], 100)


if __name__ == "__main__":
    unittest.main()
