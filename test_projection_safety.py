import math
import unittest

from player_availability import adjust_injury_workload, validate_player
from player_projections import (
    project_quarterback,
    project_receiver,
    project_player_workload,
)


class TestProjectionInputSafety(unittest.TestCase):
    def setUp(self):
        self.qb = {
            "name": "Example QB",
            "team": "BUF",
            "position": "QB",
            "status": "active",
            "starter": True,
        }
        self.receiver = dict(self.qb, name="Example WR", position="WR")

    def test_qb_formula_retained(self):
        self.assertEqual(
            project_quarterback(self.qb, 24, 11.5)["passing_yards"], 276.0
        )

    def test_invalid_qb_completions_rejected(self):
        for bad in (-1, float("nan"), float("inf"), True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                project_quarterback(self.qb, bad, 11.5)

    def test_catch_rate_cannot_exceed_one(self):
        with self.assertRaises(ValueError):
            project_receiver(self.receiver, 10, 1.5, 12)

    def test_nan_workload_rejected(self):
        with self.assertRaises(ValueError):
            project_player_workload(self.receiver, float("nan"))

    def test_infinite_injury_workload_rejected(self):
        with self.assertRaises(ValueError):
            adjust_injury_workload(self.qb, float("inf"))

    def test_invalid_team_rejected(self):
        with self.assertRaises(ValueError):
            validate_player(dict(self.qb, team="NOT_A_TEAM"))

    def test_unverified_player_still_blocked(self):
        with self.assertRaises(ValueError):
            project_quarterback(dict(self.qb, status="unknown"), 20, 12)


if __name__ == "__main__":
    unittest.main()
