import unittest
from player_prop_simulator import project_player_stats, simulate_player_prop

class TestPlayerPropSimulator(unittest.TestCase):
    def setUp(self):
        self.wr = {'name':'Test WR','team':'BUF','position':'WR','status':'active','starter':True}
        self.workload = {'projected_snaps':65,'projected_routes':40,'projected_targets':9,'projected_carries':0,'red_zone_opportunities':3}

    def test_receiver_projection(self):
        result = project_player_stats(self.wr,self.workload,{'catch_rate':0.7,'yards_per_reception':12.0})
        self.assertEqual(result['projected_stats']['receptions'],6.3)
        self.assertEqual(result['projected_stats']['receiving_yards'],75.6)

    def test_questionable_player_blocked(self):
        player=dict(self.wr,status='questionable')
        with self.assertRaises(ValueError):
            project_player_stats(player,self.workload,{'catch_rate':0.7,'yards_per_reception':12})

    def test_prop_reproducible_and_probabilities_sum(self):
        p=project_player_stats(self.wr,self.workload,{'catch_rate':0.7,'yards_per_reception':12})
        a=simulate_player_prop(p,'receiving_yards',70.5,trials=5000,seed=71)
        b=simulate_player_prop(p,'receiving_yards',70.5,trials=5000,seed=71)
        self.assertEqual(a,b)
        self.assertAlmostEqual(a['over_probability']+a['under_probability']+a['push_probability'],100.0,places=2)

if __name__ == '__main__':
    unittest.main()
