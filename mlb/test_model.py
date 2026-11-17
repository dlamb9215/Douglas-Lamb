import unittest
from datetime import datetime, timezone, timedelta

from mlb.model import (
    project_one_plus_hit, shrunk_batter_hit_rate, shrunk_pitcher_hit_rate,
    validate_confirmed_lineup, simulate_one_plus_hit,
)


class MLBModelTests(unittest.TestCase):
    def test_shrunk_rates_are_bounded(self):
        self.assertGreater(shrunk_batter_hit_rate(0, 100), 0)
        self.assertLess(shrunk_batter_hit_rate(30, 100), 1)
        self.assertGreater(shrunk_pitcher_hit_rate(0, 100), 0)

    def test_project_one_plus_hit(self):
        result = project_one_plus_hit(
            batter_hits=50, batter_pa=180, pitcher_hits_allowed=80,
            pitcher_bf=300, batting_order=2,
        )
        self.assertGreater(result["one_plus_hit_probability"], 0)
        self.assertLess(result["one_plus_hit_probability"], 1)
        self.assertEqual(result["model_status"], "BASELINE_ONLY_NOT_CALIBRATED")

    def test_invalid_stats_rejected(self):
        with self.assertRaises(ValueError):
            shrunk_batter_hit_rate(20, 10)

    def test_lineup_requires_verified_https_source_and_both_teams(self):
        now = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
        batters = [{"player_id": i, "batting_order": i} for i in range(1, 10)]
        payload = {
            "gamePk": 123, "confirmed": True, "source_url": "https://www.mlb.com/lineups",
            "checked_at_utc": (now - timedelta(minutes=10)).isoformat(),
            "teams": {
                "home": {"batters": batters, "starting_pitcher_id": 101},
                "away": {"batters": [{"player_id": i+20, "batting_order": i} for i in range(1, 10)],
                         "starting_pitcher_id": 202},
            },
        }
        result = validate_confirmed_lineup(payload, 123, now=now)
        self.assertEqual(result["lineup_age_hours"], 0.17)
        payload["source_url"] = "http://example.com"
        with self.assertRaises(ValueError):
            validate_confirmed_lineup(payload, 123, now=now)

    def test_lineup_expiration_and_game_identity(self):
        now = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
        payload = {"gamePk": 1, "confirmed": True, "source_url": "https://mlb.com",
                   "checked_at_utc": (now-timedelta(hours=4)).isoformat(),
                   "teams": {}}
        with self.assertRaises(ValueError):
            validate_confirmed_lineup(payload, 1, now=now)
        with self.assertRaises(ValueError):
            validate_confirmed_lineup(payload, 2, now=now)

    def test_monte_carlo_tracks_analytic_probability(self):
        result = simulate_one_plus_hit(0.25, 4, trials=50000, seed=17)
        self.assertLess(abs(result["simulated_probability"] - result["analytic_probability"]), 0.02)

    def test_fractional_pa_monte_carlo_has_correct_expected_value(self):
        result = simulate_one_plus_hit(0.55, 0.5, trials=100000, seed=31)
        self.assertAlmostEqual(result["analytic_probability"], 1 - (1 - 0.55) ** 0.5)
        self.assertLess(abs(result["simulated_probability"] - result["analytic_probability"]), 0.01)

    def test_fractional_plate_appearance_simulation_matches_analytic_probability(self):
        result = simulate_one_plus_hit(0.24, 4.35, trials=100000, seed=29)
        self.assertLess(abs(result["simulated_probability"] - result["analytic_probability"]), 0.015)


if __name__ == "__main__":
    unittest.main()
