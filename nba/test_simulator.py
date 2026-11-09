import unittest

from nba.simulator import (
    TeamStats,
    matchup_projection,
    simulate,
    implied_probability,
    _decision,
)


def team(code, **updates):
    data = {
        "name": code,
        "games_played": 10,
        "pace": 99,
        "off_rating": 115,
        "def_rating": 112,
        "efg_pct": 0.54,
        "tov_pct": 0.135,
        "orb_pct": 0.265,
        "ft_rate": 0.25,
        "opp_efg_pct": 0.54,
        "opp_tov_pct": 0.135,
        "opp_orb_pct": 0.265,
        "opp_ft_rate": 0.25,
    }
    data.update(updates)
    return TeamStats.from_dict(code, data)


class TestNBAEngine(unittest.TestCase):
    def test_projection(self):
        result = matchup_projection(team("BOS"), team("NYK"))
        self.assertGreater(result["home_points"], 0)
        self.assertGreater(result["total_points"], result["home_points"])

    def test_moneyline_and_overtime_resolve_all_games(self):
        result = simulate(team("BOS"), team("NYK"), 50000, 17)
        self.assertGreaterEqual(result["home_win"], 0)
        self.assertLessEqual(result["home_win"], 100)
        self.assertAlmostEqual(result["home_win"] + result["away_win"], 100, places=8)
        self.assertEqual(len(result["home_win_ci"]), 2)
        self.assertLessEqual(result["home_win_ci"][0], result["home_win"])
        self.assertGreaterEqual(result["home_win_ci"][1], result["home_win"])

    def test_market_probabilities(self):
        result = simulate(team("BOS"), team("NYK"), 25000, 7, -2.5, 220.5)
        for key in ("home_cover", "away_cover", "over", "under"):
            self.assertGreaterEqual(result[key], 0)
            self.assertLessEqual(result[key], 100)
        self.assertAlmostEqual(
            result["home_cover"] + result["away_cover"] + result["spread_push"],
            100, places=6
        )
        self.assertAlmostEqual(
            result["over"] + result["under"] + result["total_push"],
            100, places=6
        )

    def test_seed_reproducible(self):
        first = simulate(team("BOS"), team("NYK"), 5000, 123)
        second = simulate(team("BOS"), team("NYK"), 5000, 123)
        self.assertEqual(first, second)

    def test_different_seed(self):
        first = simulate(team("BOS"), team("NYK"), 5000, 123)
        second = simulate(team("BOS"), team("NYK"), 5000, 456)
        self.assertNotEqual(first, second)

    def test_neutral_site_removes_home_court_advantage(self):
        h,w=team("BOS"),team("NYK")
        normal=matchup_projection(h,w)
        neutral=matchup_projection(h,w,neutral_site=True)
        self.assertAlmostEqual(normal["home_court_points"],1.35)
        self.assertEqual(neutral["home_court_points"],0)
        self.assertAlmostEqual(normal["home_margin"]-neutral["home_margin"],1.35)

    def test_away_only_recent_pace_is_used_and_first_half_ml_sums(self):
        h,w=team("BOS"),team("NYK",recent_pace=106)
        p=matchup_projection(h,w)
        self.assertGreater(p["pace"],100)
        r=simulate(h,w,10000,13)
        first=r["first_half"]
        self.assertAlmostEqual(first["home_win"]+first["away_win"]+first["tie"],100,places=6)

    def test_invalid_pace(self):
        with self.assertRaises(ValueError):
            team("BAD", pace=150)

    def test_percent_normalization(self):
        self.assertAlmostEqual(team("BOS", efg_pct=54).efg_pct, 0.54)

    def test_first_half_outputs(self):
        result = simulate(team("BOS"), team("NYK"), 10000, 1, spread=-2.5, total=220.5)
        first_half = result["first_half"]
        self.assertGreater(first_half["home_avg"], 0)
        self.assertIn("home_cover", first_half)
        self.assertIn("over", first_half)
        self.assertAlmostEqual(
            first_half["home_cover"] + first_half["away_cover"] + first_half["spread_push"],
            100, places=6
        )
        self.assertAlmostEqual(
            first_half["over"] + first_half["under"] + first_half["total_push"],
            100, places=6
        )
        self.assertEqual(len(result["home_cover_ci"]), 2)

    def test_odds_conversion(self):
        self.assertAlmostEqual(implied_probability(-110), 110 / 210)
        self.assertAlmostEqual(implied_probability(150), 0.4)
        with self.assertRaises(ValueError):
            implied_probability(0)

    def test_zero_trials(self):
        with self.assertRaises(ValueError):
            simulate(team("BOS"), team("NYK"), 0)

    def test_rest_travel_and_injury_inputs_change_projection(self):
        home, away = team("BOS"), team("NYK")
        base = matchup_projection(home, away)
        changed = matchup_projection(
            home, away, home_rest=0, away_rest=3,
            home_travel=2000, home_injury_points=-4
        )
        self.assertLess(changed["home_points"], base["home_points"])
        self.assertGreater(changed["away_points"], base["away_points"])

    def test_recent_form_and_venue_features_are_supported(self):
        home = team("BOS", recent_off_rating=120, home_off_rating=119)
        away = team("NYK", recent_off_rating=110, road_def_rating=115)
        result = matchup_projection(home, away)
        self.assertGreater(result["home_points"], 0)

    def test_three_point_shot_profile_is_used_conservatively(self):
        home = team("BOS", three_pa_rate=0.50, fg3_pct=0.40)
        away = team("NYK", opp_three_pa_rate=0.44, opp_fg3_pct=0.39)
        baseline = matchup_projection(team("BOS"), team("NYK"))
        adjusted = matchup_projection(home, away)
        self.assertGreater(adjusted["home_points"], baseline["home_points"])
        self.assertLess(adjusted["home_points"] - baseline["home_points"], 2.0)

    def test_decision_requires_probability_and_line_edge(self):
        self.assertEqual(_decision(58, 2), "LEAN")
        self.assertEqual(_decision(54, 4), "PASS")
        self.assertEqual(_decision(60, 0.5), "PASS")


if __name__ == "__main__":
    unittest.main()
