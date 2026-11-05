import unittest
import random
from nhl_simulator import TeamStats, poisson, expected_goals, run_simulation, NHL_TEAMS

class NHLModelTests(unittest.TestCase):
    def test_all_32_team_codes_exist(self):
        self.assertEqual(len(NHL_TEAMS), 32)
    def test_poisson_nonnegative_and_reproducible(self):
        a = poisson(3.0, random.Random(7))
        b = poisson(3.0, random.Random(7))
        self.assertGreaterEqual(a, 0)
        self.assertEqual(a, b)
    def test_expected_goals_home_advantage(self):
        h = TeamStats("BOS","Boston",gf=3.2,ga=2.8)
        d = TeamStats("NYR","New York",gf=3.0,ga=3.1)
        self.assertGreater(expected_goals(h,d,True), expected_goals(h,d,False))
    def test_simulation_reproducible_and_probabilities_bounded(self):
        h = TeamStats("BOS","Boston")
        a = TeamStats("NYR","New York")
        x = run_simulation(h,a,1000,123)
        y = run_simulation(h,a,1000,123)
        self.assertEqual(x,y)
        self.assertAlmostEqual(x["home"]["win_pct_including_ot_proxy"] + x["away"]["win_pct_including_ot_proxy"],100.0,places=1)
        self.assertGreaterEqual(x["total_goals_over"]["5.5"],0)
        self.assertLessEqual(x["total_goals_over"]["5.5"],100)
    def test_rejects_too_few_trials(self):
        with self.assertRaises(ValueError):
            run_simulation(TeamStats("BOS","Boston"),TeamStats("NYR","New York"),100)

if __name__ == "__main__":
    unittest.main()
