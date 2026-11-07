import unittest
from ncaa.engine import MarketLines, TeamProfile, simulate_game
from ncaa.data import get_profile, load_profiles
from ncaa.scenarios import run_sensitivity_scenarios


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.home = TeamProfile(
            "Home U", points_for=34, points_against=20,
            yards_per_play=6.5, yards_per_play_allowed=5.0,
            plays_per_game=72, turnovers_per_game=1.0,
            takeaways_per_game=1.8, explosive_play_rate=.16,
            success_rate=.48, strength_rating=8, games_sampled=9,
            yards_per_pass_attempt=8.4, yards_per_carry=5.1,
            opponent_yards_per_completion=5.8, opponent_yards_per_carry_allowed=3.7,
            pass_yards_per_game=285, rush_yards_per_game=190,
            source="test data",
        )
        self.away = TeamProfile(
            "Away U", points_for=23, points_against=28,
            yards_per_play=5.2, yards_per_play_allowed=6.1,
            plays_per_game=68, turnovers_per_game=1.8,
            takeaways_per_game=1.0, explosive_play_rate=.09,
            success_rate=.38, strength_rating=-3, games_sampled=8,
            source="test data",
        )

    def test_reproducible(self):
        a = simulate_game(self.home, self.away, 5000, seed=44)
        b = simulate_game(self.home, self.away, 5000, seed=44)
        self.assertEqual(a, b)

    def test_probabilities_are_bounded(self):
        result = simulate_game(self.home, self.away, 3000,
                               MarketLines(-6.5, 51.5), seed=3)
        for key in ("home_win_probability", "away_win_probability",
                    "home_cover_probability", "away_cover_probability",
                    "over_probability", "under_probability"):
            self.assertGreaterEqual(result["market"].get(key, result.get(key, 0)), 0)
            self.assertLessEqual(result["market"].get(key, result.get(key, 0)), 1)
        self.assertAlmostEqual(result["home_win_probability"] +
                               result["away_win_probability"], 1.0)
        self.assertAlmostEqual(result["market"]["over_probability"] +
                               result["market"]["under_probability"], 1.0)

    def test_stronger_team_projects_higher(self):
        result = simulate_game(self.home, self.away, 12000, seed=11)
        self.assertGreater(result["projected_score"]["Home U"],
                           result["projected_score"]["Away U"])
        self.assertGreater(result["home_win_probability"], .5)

    def test_first_half_and_score_ranges_present(self):
        result = simulate_game(self.home, self.away, 2500, seed=17)
        self.assertIn("projected_first_half_score", result)
        self.assertIn("score_ranges", result)
        self.assertIn("first_half_win_probability_home", result)
        self.assertGreaterEqual(result["first_half_win_probability_home"], 0)
        self.assertLessEqual(result["first_half_win_probability_home"], 1)

    def test_push_probabilities_account_for_pushes(self):
        result = simulate_game(self.home, self.away, 2000,
                               MarketLines(0, 0), seed=19)
        market = result["market"]
        self.assertAlmostEqual(
            market["home_cover_probability"] + market["away_cover_probability"] +
            market["spread_push_probability"], 1.0)
        self.assertAlmostEqual(
            market["over_probability"] + market["under_probability"] +
            market["total_push_probability"], 1.0)

    def test_team_comparison_includes_pass_rush_and_defense(self):
        result = simulate_game(self.home, self.away, 1000, seed=23)
        comparison = result["team_comparison"]["Home U"]
        self.assertEqual(comparison["offense"]["pass_yards_per_game"], 285)
        self.assertEqual(comparison["offense"]["rush_yards_per_game"], 190)
        self.assertEqual(comparison["defense"]["total_yards_per_play_allowed"],
                         self.home.yards_per_play_allowed)
        self.assertIn("turnovers", comparison)

    def test_sensitivity_scenarios_are_explicit_and_complete(self):
        result = run_sensitivity_scenarios(self.home, self.away, 500, seed=90)
        scenarios = result["scenarios"]
        self.assertEqual(len(scenarios), 6)
        self.assertIn("baseline", scenarios)
        self.assertIn("home_offense_down_10pct", scenarios)
        self.assertIn("slow_pace_down_8pct", scenarios)
        self.assertIn("not weighted or calibrated", result["interpretation"])
        for scenario in scenarios.values():
            self.assertGreaterEqual(scenario["home_win_probability"], 0)
            self.assertLessEqual(scenario["home_win_probability"], 1)

    def test_invalid_trial_count_rejected(self):
        with self.assertRaises(ValueError):
            simulate_game(self.home, self.away, 0)

    def test_profile_validation(self):
        with self.assertRaises(ValueError):
            TeamProfile("Bad U", yards_per_play=-1).validate()

    def test_bad_cfbd_profile_is_blocked(self):
        bad = TeamProfile(
            "Bad Data U", plays_per_game=36.9, yards_per_play=11.2,
            source="CollegeFootballData API", as_of="2026-11-07",
            games_sampled=8,
        )
        with self.assertRaisesRegex(ValueError, "invalid plays/game"):
            get_profile("Bad Data U", {"bad data u": bad})

    def test_missing_profile_uses_flagged_prior(self):
        profile = get_profile("Unknown U", {})
        self.assertEqual(profile.games_sampled, 0)
        result = simulate_game(profile, self.away, 100, seed=2)
        self.assertTrue(result["data_quality"]["warnings"])


if __name__ == "__main__":
    unittest.main()
