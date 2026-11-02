
import unittest

from player_projections import (
    project_quarterback,
    project_running_back,
    project_receiver,
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


if __name__ == "__main__":
    unittest.main()
