import unittest
from nhl.elite import season_id, normalize_team, matchup_means, poisson, simulate, TEAMS, evaluate_two_way_market, attach_team_ranks, attach_team_summary, validate_odds_context

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
    def test_team_rankings_attach(self):
        attach_team_ranks(self.teams)
        self.assertIn("goals_for_per_game",self.teams["BOS"]["rankings"])
        self.assertEqual(self.teams["BOS"]["rankings"]["goals_for_per_game"],2)
    def test_goal_means_positive(self):
        h,a,_=matchup_means(self.teams["BOS"],self.teams["FLA"])
        self.assertGreater(h,0); self.assertGreater(a,0)
    def test_poisson_nonnegative(self):
        import random
        self.assertGreaterEqual(poisson(random.Random(1),3.1),0)
    def test_rejects_invalid_trials(self):
        with self.assertRaises(ValueError):
            simulate("BOS","FLA",self.teams,[],[],self.rosters,trials=10)
    def test_simulation_returns_bounded_market_probabilities(self):
        out=simulate("BOS","FLA",self.teams,[],[],self.rosters,trials=1000,seed=5)
        self.assertEqual(out["trials"],1000)
        self.assertAlmostEqual(out["moneyline_pct"]["home"]+out["moneyline_pct"]["away"],100.0)
        self.assertGreaterEqual(out["total_pct"]["over"],0)
        self.assertLessEqual(out["total_pct"]["over"],100)
    def test_invalid_selected_goalie_rejected(self):
        with self.assertRaises(ValueError):
            simulate("BOS","FLA",self.teams,[],[],self.rosters,trials=1000,home_goalie_id="invalid")
    def test_odds_context_requires_source_and_timezone_aware_timestamp(self):
        from datetime import datetime, timezone
        now = datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            validate_odds_context([-110, 100], None, "2026-11-18T17:00:00Z", now=now)
        with self.assertRaises(ValueError):
            validate_odds_context([-110, 100], "Example Book", "2026-11-18T17:00:00", now=now)
        with self.assertRaises(ValueError):
            validate_odds_context([-110, 100], "Example Book", "2026-11-18T01:00:00Z", now=now)
        valid = validate_odds_context([-110, 100], "Example Book", "2026-11-18T17:00:00Z", now=now)
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["status"], "FRESH_QUOTE")

    def test_no_odds_context_is_not_mislabeled_ready(self):
        result = validate_odds_context([0, 0], None, None)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "NO_ODDS_SUPPLIED")

    def test_no_vig_odds_comparison(self):
        out=evaluate_two_way_market(60,40,-120,110)
        self.assertIn("no_vig_market_pct",out)
        self.assertGreater(out["no_vig_market_pct"]["side_a"],0)
    def test_team_rates_from_standings_totals(self):
        x=normalize_team({"teamAbbrev":"FLA","gamesPlayed":10,"goalsFor":35,"goalsAgainst":28})
        self.assertEqual(x["team"],"FLA")
        self.assertEqual(x["gf"],3.5)
        self.assertEqual(x["ga"],2.8)
    def test_nhl_standings_singular_goal_fields(self):
        x=normalize_team({"teamAbbrev":{"default":"FLA"},"gamesPlayed":10,"goalFor":35,"goalAgainst":28})
        self.assertEqual(x["team"],"FLA")
        self.assertEqual(x["gf"],3.5)
        self.assertEqual(x["ga"],2.8)
    def test_team_summary_adds_shots_special_teams_and_faceoffs(self):
        teams = {
            "BOS": {"team": "BOS", "games": 20, "gf": 3.2, "ga": 2.7},
            "FLA": {"team": "FLA", "games": 20, "gf": 3.4, "ga": 2.9},
        }
        rows = [
            {"teamAbbrev": "BOS", "shotsForPerGame": 31.4, "shotsAgainstPerGame": 27.2,
             "powerPlayPct": 0.235, "penaltyKillPct": 0.812, "faceoffWinPct": 0.518},
            {"teamAbbrev": "FLA", "shotsPerGame": 32.1, "shotsAllowedPerGame": 28.4,
             "powerPlayPercentage": 22.5, "penaltyKillPercentage": 80.1,
             "faceOffWinPercentage": 51.2},
        ]
        attach_team_summary(teams, rows)
        self.assertEqual(teams["BOS"]["sf"], 31.4)
        self.assertEqual(teams["BOS"]["sa"], 27.2)
        self.assertAlmostEqual(teams["BOS"]["pp"], 23.5)
        self.assertAlmostEqual(teams["BOS"]["pk"], 81.2)
        self.assertAlmostEqual(teams["BOS"]["fo"], 51.8)
        self.assertEqual(teams["FLA"]["sf"], 32.1)
        self.assertEqual(teams["FLA"]["sa"], 28.4)
        self.assertTrue(teams["BOS"]["team_summary_available"])
        self.assertTrue(teams["FLA"]["team_summary_available"])

    def test_missing_team_summary_features_remain_explicitly_missing(self):
        teams = {"BOS": {"team": "BOS", "games": 20, "gf": 3.2, "ga": 2.7}}
        attach_team_summary(teams, [])
        self.assertFalse(teams["BOS"]["team_summary_available"])
        self.assertEqual(set(teams["BOS"]["team_summary_missing_fields"]), {"sf", "sa", "pp", "pk", "fo"})
        self.assertIsNone(teams["BOS"]["pp"])

    def test_team_rates_not_fabricated(self):
        x=normalize_team({"teamAbbrev":"BOS","gamesPlayed":20})
        self.assertIsNone(x["gf"]); self.assertIsNone(x["ga"])

if __name__=="__main__": unittest.main()
