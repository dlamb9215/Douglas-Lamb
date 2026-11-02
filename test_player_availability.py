
import unittest

from player_projections import (
    project_quarterback,
    project_running_back,
    project_receiver,
    project_player_workload,
)



class TestPlayerProjections(unittest.TestCase):

    def setUp(self):
        self.active_qb = {
            "name": "Test QB",
            "team": "BUF",
            "position": "QB",
            "status": "active",
            "starter": True,
        }

        self.questionable_rb = {
            "name": "Test RB",
            "team": "BUF",
            "position": "RB",
            "status": "questionable",
            "starter": True,
        }

        self.out_receiver = {
            "name": "Test WR",
            "team": "BUF",
            "position": "WR",
            "status": "out",
            "starter": False,
        }

    def test_active_qb_projection(self):
        result = project_quarterback(
            self.active_qb, 24, 11.5
        )

        self.assertEqual(result["passing_yards"], 276.0)

    def test_questionable_player_blocked(self):
        with self.assertRaises(ValueError):
            project_running_back(
                self.questionable_rb, 15, 4.5
            )

    def test_out_player_blocked(self):
        with self.assertRaises(ValueError):
            project_receiver(
                self.out_receiver, 8, 0.65, 12
            )


    def test_active_player_workload(self):
        result = project_player_workload(
            self.active_qb,
            projected_snaps=65,
            projected_routes=0,
            projected_targets=0,
            projected_carries=0,
            red_zone_opportunities=3,
        )

        self.assertEqual(result["projected_snaps"], 65)
        self.assertEqual(result["red_zone_opportunities"], 3)

    def test_workload_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            project_player_workload(
                self.active_qb,
                projected_snaps=120,
            )

    def test_workload_rejects_questionable_player(self):
        with self.assertRaises(ValueError):
            project_player_workload(
                self.questionable_rb,
                projected_snaps=50,
                projected_carries=15,
            )

if __name__ == "__main__":
    unittest.main()
