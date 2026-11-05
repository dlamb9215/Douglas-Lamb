import unittest
from datetime import datetime, timezone, timedelta

from pregame_context import build_pregame_report


class PregameContextTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.pool = {
            "season": self.now.year,
            "source": "nflverse",
            "retrieved_at_utc": self.now.isoformat(),
            "players": [
                {"team": "BAL", "name": "QB One", "position": "QB",
                 "depth_order": 1, "roster_status": "active",
                 "injury_status": "active"},
                {"team": "BAL", "name": "WR One", "position": "WR",
                 "depth_order": 1, "roster_status": "active",
                 "injury_status": "questionable"},
                {"team": "JAX", "name": "QB Two", "position": "QB",
                 "depth_order": 1, "roster_status": "active",
                 "injury_status": "active"},
            ],
        }

    def test_report_keeps_depth_chart_distinct_from_final_starters(self):
        report = build_pregame_report(self.pool, "BAL", "JAX", now=self.now)
        self.assertTrue(report["team_simulation_ready"])
        self.assertFalse(report["player_props_ready"])
        self.assertFalse(report["teams"]["BAL"]["official_starting_quarterback_confirmed"])
        self.assertEqual(report["teams"]["BAL"]["reported_injuries"][0]["status"], "questionable")

    def test_missing_active_qb1_blocks_team_simulation(self):
        self.pool["players"][0]["depth_order"] = 99
        report = build_pregame_report(self.pool, "BAL", "JAX", now=self.now)
        self.assertFalse(report["team_simulation_ready"])
        self.assertTrue(report["team_simulation_blockers"])

    def test_out_qb1_blocks_team_simulation(self):
        self.pool["players"][0]["injury_status"] = "out"
        report = build_pregame_report(self.pool, "BAL", "JAX", now=self.now)
        self.assertFalse(report["team_simulation_ready"])

    def test_stale_player_data_is_rejected(self):
        self.pool["retrieved_at_utc"] = (self.now - timedelta(hours=40)).isoformat()
        with self.assertRaisesRegex(ValueError, "stale"):
            build_pregame_report(self.pool, "BAL", "JAX", now=self.now)

    def test_invalid_matchup_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different valid"):
            build_pregame_report(self.pool, "BAL", "BAL", now=self.now)

    def test_wrong_source_is_rejected(self):
        self.pool["source"] = "unknown"
        with self.assertRaisesRegex(ValueError, "source"):
            build_pregame_report(self.pool, "BAL", "JAX", now=self.now)


if __name__ == "__main__":
    unittest.main()
