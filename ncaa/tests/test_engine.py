import unittest
from ncaa.engine import MarketLines, TeamProfile, simulate_game
from ncaa.data import get_profile, load_profiles


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.home = TeamProfile(
            "Home U", points_for=34, points_against=20,
            yards_per_play=6.5, yards_per_play_allowed=5.0,
            plays_per_game=72, turnovers_per_game=1.0,
            takeaways_per_game=1.8, explosive_play_rate=.16,
            success_rate=.48, strength_rating=8, games_sampled=9,
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

    def test_invalid_trial_count_rejected(self):
        with self.assertRaises(ValueError):
            simulate_game(self.home, self.away, 0)

    def test_profile_validation(self):
        with self.assertRaises(ValueError):
            TeamProfile("Bad U", yards_per_play=-1).validate()

    def test_missing_profile_uses_flagged_prior(self):
        profile = get_profile("Unknown U", {})
        self.assertEqual(profile.games_sampled, 0)
        result = simulate_game(profile, self.away, 100, seed=2)
        self.assertTrue(result["data_quality"]["warnings"])


if __name__ == "__main__":
    unittest.main()
