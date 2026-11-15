import unittest
from nhl.elite import season_id, normalize_team, matchup_means, poisson, simulate, TEAMS

class EliteNHLTests(unittest.TestCase):
    def setUp(self):
        self.teams={
          "BOS":{"team":"BOS","games":20,"gf":3.2,"ga":2.7,"sf":31.0,"sa":27.0,"pp":24.0,"pk":82.0,"fo":51.0},
          "FLA":{"team":"FLA","games":20,"gf":3.4,"ga":2.9,"sf":32.0,"sa":28.0,"pp":22.0,"pk":80.0,"fo":52.0}}
        self.rosters={"BOS":{"forwards":[],"defensemen":[],"goalies":[]},"FLA":{"forwards":[],"defensemen":[],"goalies":[]}}
    def test_all_teams(self): self.assertEqual(len(TEAMS),32)
    def test_season_rollover(self):
        from datetime import datetime, timezone
        self.assertEqual(season_id(datetime(2026,11,1,tzinfo=timezone.utc)),20262027)
        self.assertEqual(season_id(datetime(2027,7,1,tzinfo=timezone.utc)),20262027)
    def test_normalize_team(self):
        x=normalize_team({"teamAbbrev":"BOS","gamesPlayed":20,"goalsForPerGame":3.1,"goalsAgainstPerGame":2.8})
        self.assertEqual(x["team"],"BOS"); self.assertEqual(x["games"],20)
    def test_goal_means_positive(self):
        h,a,_=matchup_means(self.teams["BOS"],self.teams["FLA"])
        self.assertGreater(h,0); self.assertGreater(a,0)
    def test_poisson_nonnegative(self):
        import random
        self.assertGreaterEqual(poisson(random.Random(1),3.1),0)
    def test_rejects_invalid_trials(self):
        with self.assertRaises(ValueError):
            simulate("BOS","FLA",self.teams,[],[],self.rosters,trials=10)
    def test_team_rates_not_fabricated(self):
        x=normalize_team({"teamAbbrev":"BOS","gamesPlayed":20})
        self.assertIsNone(x["gf"]); self.assertIsNone(x["ga"])

if __name__=="__main__": unittest.main()
