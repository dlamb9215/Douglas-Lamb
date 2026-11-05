import unittest
from nba.simulator import TeamStats, matchup_projection, simulate, implied_probability, _decision

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
        for k in ("home_cover","away_cover","over","under"):
            self.assertGreaterEqual(r[k],0); self.assertLessEqual(r[k],100)
        self.assertAlmostEqual(r["home_cover"]+r["away_cover"]+r["spread_push"],100,places=6)
        self.assertAlmostEqual(r["over"]+r["under"]+r["total_push"],100,places=6)
        self.assertIn("home_win",r)
        self.assertIn("away_win",r)
        self.assertAlmostEqual(r["home_win"]+r["away_win"]+r["win_tie"],100,places=6)
    def test_seed_reproducible(self):
        self.assertEqual(simulate(team("BOS"),team("NYK"),5000,123),simulate(team("BOS"),team("NYK"),5000,123))
    def test_different_seed(self):
        self.assertNotEqual(simulate(team("BOS"),team("NYK"),5000,123),simulate(team("BOS"),team("NYK"),5000,456))
    def test_invalid_pace(self):
        with self.assertRaises(ValueError): team("BAD",pace=150)
    def test_percent_normalization(self):
        self.assertAlmostEqual(team("BOS",efg_pct=54).efg_pct,.54)
    def test_first_half_outputs(self):
        r=simulate(team("BOS"),team("NYK"),10000,1,spread=-2.5,total=220.5)
        self.assertGreater(r["first_half"]["home_avg"],0)
        self.assertIn("home_cover",r["first_half"])
        self.assertIn("over",r["first_half"])
        self.assertAlmostEqual(r["first_half"]["home_cover"]+r["first_half"]["away_cover"]+r["first_half"]["spread_push"],100,places=6)
        self.assertAlmostEqual(r["first_half"]["over"]+r["first_half"]["under"]+r["first_half"]["total_push"],100,places=6)
        self.assertEqual(len(r["home_cover_ci"]),2)
        self.assertLess(r["home_cover_ci"][0],r["home_cover_ci"][1])
    def test_odds_conversion(self):
        self.assertAlmostEqual(implied_probability(-110),110/210)
        self.assertAlmostEqual(implied_probability(150),.4)
        with self.assertRaises(ValueError): implied_probability(0)
    def test_zero_trials(self):
        with self.assertRaises(ValueError): simulate(team("BOS"),team("NYK"),0)
    def test_rest_travel_and_injury_inputs_change_projection(self):
        h,w=team("BOS"),team("NYK")
        base=matchup_projection(h,w)
        changed=matchup_projection(h,w,home_rest=0,away_rest=3,home_travel=2000,home_injury_points=-4)
        self.assertLess(changed["home_points"],base["home_points"])
        self.assertGreater(changed["away_points"],base["away_points"])
    def test_recent_pace_uses_season_baseline_when_one_team_has_no_recent_sample(self):
        h=team("BOS",recent_pace=105)
        w=team("NYK",recent_pace=None)
        result=matchup_projection(h,w)
        expected=.8*99+.2*((105+99)/2)
        self.assertAlmostEqual(result["pace"],expected)

    def test_recent_form_and_venue_features_are_supported(self):
        h=team("BOS",recent_off_rating=120,home_off_rating=119)
        w=team("NYK",recent_off_rating=110,road_def_rating=115)
        r=matchup_projection(h,w)
        self.assertGreater(r["home_points"],0)
    def test_three_point_shot_profile_is_used_conservatively(self):
        h=team("BOS",three_pa_rate=.50,fg3_pct=.40)
        w=team("NYK",opp_three_pa_rate=.44,opp_fg3_pct=.39)
        baseline=matchup_projection(team("BOS"),team("NYK"))
        adjusted=matchup_projection(h,w)
        self.assertGreater(adjusted["home_points"],baseline["home_points"])
        self.assertLess(adjusted["home_points"]-baseline["home_points"],2.0)
    def test_decision_requires_probability_and_line_edge(self):
        self.assertEqual(_decision(58,2),"LEAN")
        self.assertEqual(_decision(54,4),"PASS")
        self.assertEqual(_decision(60,.5),"PASS")
if __name__=="__main__": unittest.main()
