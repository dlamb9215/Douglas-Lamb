import unittest
from nfl_player_data import build_player_pool


class TestNFLPlayerData(unittest.TestCase):
    def setUp(self):
        self.stats = [
            {"player_id":"P1","player_display_name":"Test Receiver","position":"WR",
             "recent_team":"BUF","season":"2026","week":"8","targets":"10",
             "receptions":"7","receiving_yards":"84","receiving_tds":"1"},
            {"player_id":"P1","player_display_name":"Test Receiver","position":"WR",
             "recent_team":"BUF","season":"2026","week":"7","targets":"8",
             "receptions":"6","receiving_yards":"72","receiving_tds":"0"},
        ]
        self.rosters = [{"gsis_id":"P1","status":"ACT"}]
        self.depth = [{"gsis_id":"P1","depth_position":"WR","depth_order":"1"}]
        self.injuries = [{"gsis_id":"P1","team":"BUF","season":"2026","week":"8","report_status":""}]
        self.snaps = [
            {"player":"Test Receiver","team":"BUF","season":"2026","week":"8",
             "offense_snaps":"55","offense_pct":"82.0"},
            {"player":"Test Receiver","team":"BUF","season":"2026","week":"7",
             "offense_snaps":"50","offense_pct":"75.0"},
        ]

    def test_joins_usage_roster_depth_injury_and_snaps(self):
        players = build_player_pool(
            self.stats,self.rosters,self.depth,self.injuries,2026,5,self.snaps
        )
        self.assertEqual(len(players),1)
        player = players[0]
        self.assertTrue(player["starter"])
        self.assertEqual(player["targets_per_game"],9.0)
        self.assertEqual(player["receiving_yards_per_game"],78.0)
        self.assertEqual(player["offense_snaps_total"],105.0)
        self.assertEqual(player["offense_snap_pct_avg"],78.5)
        self.assertEqual(player["receiving_yards_stddev_per_game"],6.0)

    def test_2025_plus_depth_chart_schema_is_read_correctly(self):
        self.depth = [{
            "gsis_id": "P1", "team": "BUF",
            "dt": "2026-11-05T12:00:00Z",
            "pos_abb": "WR", "pos_rank": "1",
        }]
        player = build_player_pool(
            self.stats,self.rosters,self.depth,self.injuries,2026,5,self.snaps
        )[0]
        self.assertTrue(player["starter"])
        self.assertEqual(player["depth_order"], 1)

    def test_latest_team_injury_week_overrides_old_out_designation(self):
        self.injuries = [
            {"gsis_id":"P1","team":"BUF","season":"2026","week":"7","report_status":"Out"},
            {"gsis_id":"P1","team":"BUF","season":"2026","week":"8","report_status":"Questionable"},
        ]
        player = build_player_pool(
            self.stats,self.rosters,self.depth,self.injuries,2026,5,self.snaps
        )[0]
        self.assertEqual(player["status"], "questionable")

    def test_questionable_player_is_blocked(self):
        self.injuries[0]["report_status"] = "Questionable"
        player = build_player_pool(
            self.stats,self.rosters,self.depth,self.injuries,2026,5,self.snaps
        )[0]
        self.assertFalse(player["starter"])
        self.assertEqual(player["status"],"questionable")

    def test_doubtful_is_not_mislabeled_as_out(self):
        self.injuries[0]["report_status"] = "Doubtful"
        player = build_player_pool(
            self.stats,self.rosters,self.depth,self.injuries,2026,5,self.snaps
        )[0]
        self.assertFalse(player["starter"])
        self.assertEqual(player["status"], "doubtful")

    def test_not_first_depth_chart_player_is_blocked(self):
        self.depth[0]["depth_order"] = "2"
        player = build_player_pool(
            self.stats,self.rosters,self.depth,self.injuries,2026,5,self.snaps
        )[0]
        self.assertFalse(player["starter"])

    def test_non_active_roster_player_is_blocked(self):
        self.rosters[0]["status"] = "RES"
        player = build_player_pool(
            self.stats,self.rosters,self.depth,self.injuries,2026,5,self.snaps
        )[0]
        self.assertFalse(player["starter"])


if __name__ == "__main__":
    unittest.main()
