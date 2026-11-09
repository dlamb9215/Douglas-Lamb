import unittest
from nba.elite_analytics import (PlayerInput, simulate_player_props,
    american_implied_probability, no_vig_two_way, expected_value_per_100, scenario_grid)

def profile(**updates):
    data={"player":"Test Player","team":"BOS","status":"available","lineup_confirmed":True,
          "minutes":34,"minutes_sd":2.5,"points_per_minute":.72,
          "rebounds_per_minute":.18,"assists_per_minute":.20}
    data.update(updates)
    return data

class TestEliteAnalytics(unittest.TestCase):
    def test_eligible_player_props(self):
        result=simulate_player_props(profile(),trials=20000,seed=7,lines={"points":24.5,"pra":34.5})
        self.assertTrue(result["eligible"])
        self.assertEqual(result["trials"],20000)
        self.assertGreater(result["projections"]["points"]["mean"],0)
        self.assertAlmostEqual(result["projections"]["pra"]["over_probability"]+
                               result["projections"]["pra"]["under_probability"]+
                               result["projections"]["pra"]["push_probability"],100,places=6)

    def test_injured_and_uncertain_players_are_blocked(self):
        for status in ("out","doubtful","questionable","inactive","suspended","unknown"):
            self.assertFalse(simulate_player_props(profile(status=status))["eligible"])
        self.assertFalse(simulate_player_props(profile(lineup_confirmed=False))["eligible"])

    def test_minutes_uncertainty_gate(self):
        self.assertFalse(simulate_player_props(profile(minutes_sd=9))["eligible"])
        self.assertFalse(simulate_player_props(profile(minutes=5))["eligible"])

    def test_invalid_player_input(self):
        with self.assertRaises(ValueError):
            PlayerInput.from_dict(profile(points_per_minute=-1))
        with self.assertRaises(ValueError):
            PlayerInput.from_dict(profile(minutes=60))

    def test_odds_and_no_vig(self):
        self.assertAlmostEqual(american_implied_probability(-110),110/210)
        result=no_vig_two_way(-110,-110)
        self.assertAlmostEqual(result["over"],50)
        self.assertAlmostEqual(result["under"],50)
        self.assertGreater(result["hold_pct"],0)

    def test_expected_value(self):
        self.assertAlmostEqual(expected_value_per_100(50,100),0)
        self.assertGreater(expected_value_per_100(55,-110),0)
        with self.assertRaises(ValueError):
            expected_value_per_100(101,-110)

    def test_scenario_grid(self):
        result=scenario_grid({"home":110,"away":105},{"star_out":{"home":-5}})
        self.assertEqual(result["star_out"],{"home":105,"away":105})
        with self.assertRaises(ValueError):
            scenario_grid({"home":110},{"bad":{"away":-2}})

    def test_rejects_non_finite_player_inputs_and_lines(self):
        for field in ("minutes", "minutes_sd", "points_per_minute", "usage_multiplier"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    PlayerInput.from_dict(profile(**{field: float("nan")}))
        with self.assertRaises(ValueError):
            simulate_player_props(profile(), trials=1000, lines={"points": float("inf")})
        with self.assertRaises(ValueError):
            simulate_player_props(profile(), trials=1000, lines={"steals": 1.5})

    def test_rejects_non_finite_odds_and_scenario_values(self):
        with self.assertRaises(ValueError):
            american_implied_probability(float("nan"))
        with self.assertRaises(ValueError):
            expected_value_per_100(50, float("inf"))
        with self.assertRaises(ValueError):
            scenario_grid({"home": 110}, {"bad": {"home": float("nan")}})

if __name__=="__main__": unittest.main()
