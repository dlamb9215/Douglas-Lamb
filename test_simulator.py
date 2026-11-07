
import unittest

from main import simulate_game
from drive_simulator import simulate_drive_game, _game_script_multiplier


class TestDougSimulator(unittest.TestCase):

    def test_full_team_metric_rankings_are_available(self):
        from nfl_data import load_team_stats
        database = load_team_stats()
        self.assertIn("attempts_per_game_rank", database["BAL"]["offense"]["passing"])
        self.assertIn("yards_per_carry_rank", database["BAL"]["defense"]["rushing"])
        self.assertIn("takeaways_rank", database["BAL"]["turnovers"])
        self.assertIn("giveaways_rank", database["BAL"]["turnovers"])
        self.assertIn("differential_rank", database["BAL"]["turnovers"])
        self.assertGreaterEqual(database["BAL"]["turnovers"]["differential_rank"], 1)
        self.assertLessEqual(database["BAL"]["turnovers"]["differential_rank"], 32)

    def test_matchup_scoring_projection_uses_home_field_advantage(self):
        from nfl_data import load_team_stats, project_matchup_scoring
        from main import project_matchup_scoring as main_projection
        database = load_team_stats()
        with_home = main_projection(database, "BAL", "JAX")
        neutral = project_matchup_scoring(
            database, "BAL", "JAX", home_field_points=0
        )
        self.assertGreater(with_home["BAL"], 0)
        self.assertGreater(with_home["JAX"], 0)
        self.assertAlmostEqual(with_home["BAL"] - neutral["BAL"], 1.5)
        self.assertAlmostEqual(with_home["JAX"], neutral["JAX"])

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


    def test_seed_reproduces_same_results(self):
        first = simulate_game(24, 21, 10, 10, -3, 45, 5000, seed=123)
        second = simulate_game(24, 21, 10, 10, -3, 45, 5000, seed=123)
        self.assertEqual(first, second)

    def test_different_seeds_can_change_results(self):
        first = simulate_game(24, 21, 10, 10, -3, 45, 5000, seed=123)
        second = simulate_game(24, 21, 10, 10, -3, 45, 5000, seed=456)
        self.assertNotEqual(first, second)


    def test_probability_buckets_sum_to_one_hundred(self):
        result = simulate_drive_game(24, 21, -3, 45, trials=12000, seed=9)
        self.assertAlmostEqual(
            result["home_win"] + result["away_win"] + result["tie"],
            100.0,
            places=8,
        )
        self.assertAlmostEqual(
            result["over"] + result["under"] + result["total_push"],
            100.0,
            places=8,
        )

    def test_game_script_adjustments_are_bounded(self):
        self.assertEqual(_game_script_multiplier(0), 1.0)
        self.assertLess(_game_script_multiplier(14), 1.0)
        self.assertGreater(_game_script_multiplier(-14), 1.0)

    def test_negative_scoring_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            simulate_drive_game(-1, 20, 0, 40, trials=100)

    def test_nonpositive_trial_count_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate_drive_game(20, 20, 0, 40, trials=0)

    def test_team_standard_deviation_is_used(self):
        low_variance = simulate_drive_game(
            24, 21, -3, 45, trials=3000, seed=12, home_sd=1, away_sd=1
        )
        high_variance = simulate_drive_game(
            24, 21, -3, 45, trials=3000, seed=12, home_sd=18, away_sd=18
        )
        self.assertNotEqual(low_variance, high_variance)


    def test_turnover_rates_do_not_double_count_scoring_loss(self):
        low = simulate_drive_game(
            24, 21, -3, 45, trials=50000, seed=77,
            home_turnover_rate=0.02, away_turnover_rate=0.02
        )
        high = simulate_drive_game(
            24, 21, -3, 45, trials=50000, seed=77,
            home_turnover_rate=0.25, away_turnover_rate=0.25
        )
        self.assertNotEqual(low, high)
        # Turnovers alter game variance and win/cover distribution, but the
        # supplied scoring means already include historical turnover losses.
        # The mean score should therefore remain close, not collapse.
        low_total = low["home_avg"] + low["away_avg"]
        high_total = high["home_avg"] + high["away_avg"]
        self.assertLess(abs(low_total - high_total), 2.0)

    def test_turnover_rate_is_validated(self):
        with self.assertRaises(ValueError):
            simulate_drive_game(
                24, 21, -3, 45, trials=1000,
                home_turnover_rate=0.31
            )

    def test_overtime_is_counted_and_final_outcomes_are_valid(self):
        result = simulate_drive_game(
            20, 20, 0, 40, trials=20000, seed=88
        )
        self.assertGreaterEqual(result["overtime"], 0)
        self.assertLessEqual(result["overtime"], 100)
        self.assertGreaterEqual(result["tie"], 0)
        self.assertLessEqual(result["tie"], result["overtime"])
        self.assertLess(result["home_avg"], 30)
        self.assertLess(result["away_avg"], 30)

    def test_wilson_confidence_intervals_are_valid_and_narrow_with_more_trials(self):
        from drive_simulator import _wilson_interval
        small = _wilson_interval(50, 100)
        large = _wilson_interval(5000, 10000)
        self.assertLess(small[0], 50.0)
        self.assertGreater(small[1], 50.0)
        self.assertLess(large[0], 50.0)
        self.assertGreater(large[1], 50.0)
        self.assertLess(large[1] - large[0], small[1] - small[0])

    def test_simulation_returns_confidence_intervals_for_outcomes(self):
        result = simulate_drive_game(24, 21, -3, 45, trials=10000, seed=17)
        for key in ("home_win", "away_win", "home_cover", "away_cover", "over", "under"):
            low, high = result["probability_ci95"][key]
            self.assertGreaterEqual(low, 0.0)
            self.assertLessEqual(high, 100.0)
            self.assertLessEqual(low, result[key])
            self.assertGreaterEqual(high, result[key])
if __name__ == "__main__":
    unittest.main()
