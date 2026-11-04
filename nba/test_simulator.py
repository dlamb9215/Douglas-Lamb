import unittest
from nba.simulator import TeamStats, matchup_projection, simulate, implied_probability

def team(code, **updates):
    d={"name":code,"games_played":10,"pace":99,"off_rating":115,"def_rating":112,
       "efg_pct":.54,"tov_pct":.135,"orb_pct":.265,"ft_rate":.25,
       "opp_efg_pct":.54,"opp_tov_pct":.135,"opp_orb_pct":.265,"opp_ft_rate":.25}
    d.update(updates)
    return TeamStats.from_dict(code,d)

class TestNBAEngine(unittest.TestCase):
    def test_projection(self):
        r=matchup_projection(team("BOS"),team("NYK"))
        self.assertGreater(r["home_points"],0)
        self.assertGreater(r["total_points"],r["home_points"])
    def test_market_probabilities(self):
        r=simulate(team("BOS"),team("NYK"),25000,7,-2.5,220.5)
        for k in ("home_win","away_win","home_cover","away_cover","over","under"):
            self.assertGreaterEqual(r[k],0); self.assertLessEqual(r[k],100)
        self.assertAlmostEqual(r["home_win"]+r["away_win"],100,places=6)
    def test_seed_reproducible(self):
        self.assertEqual(simulate(team("BOS"),team("NYK"),5000,123),simulate(team("BOS"),team("NYK"),5000,123))
    def test_different_seed(self):
        self.assertNotEqual(simulate(team("BOS"),team("NYK"),5000,123),simulate(team("BOS"),team("NYK"),5000,456))
    def test_invalid_pace(self):
        with self.assertRaises(ValueError): team("BAD",pace=150)
    def test_percent_normalization(self):
        self.assertAlmostEqual(team("BOS",efg_pct=54).efg_pct,.54)
    def test_first_half(self):
        self.assertIn("home_avg",simulate(team("BOS"),team("NYK"),10000,1)["first_half"])
    def test_odds(self):
        self.assertAlmostEqual(implied_probability(-110),110/210)
        self.assertAlmostEqual(implied_probability(150),.4)
        with self.assertRaises(ValueError): implied_probability(0)
    def test_zero_trials(self):
        with self.assertRaises(ValueError): simulate(team("BOS"),team("NYK"),0)
if __name__=="__main__": unittest.main()
