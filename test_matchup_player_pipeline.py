import unittest
from matchup_player_pipeline import analyze_matchup


class TestMatchupPlayerPipeline(unittest.TestCase):
    def setUp(self):
        self.pool = {
            "source": "test-fixture",
            "retrieved_at_utc": "2026-11-03T00:00:00+00:00",
            "season": 2026,
            "last_n_weeks": 5,
            "players": [{
                "name": "Example Receiver", "team": "BUF", "position": "WR",
                "status": "active", "starter": True, "games": 5,
                "targets_per_game": 8.0, "receptions_per_game": 6.0,
                "receiving_yards_per_game": 72.0, "receiving_tds_per_game": 0.4,
                "offense_snaps_per_game": 55.0, "offense_snap_pct_avg": 80.0,
            }, {
                "name": "Questionable Player", "team": "BUF", "position": "RB",
                "status": "questionable", "starter": False, "games": 4,
                "carries_per_game": 10.0, "rushing_yards_per_game": 40.0,
            }]
        }

    def test_default_blocks_depth_chart_only_players(self):
        report = analyze_matchup("BUF", "MIA", self.pool)
        self.assertEqual(report["eligible_players"], 0)
        self.assertEqual(len(report["blocked_players"]), 2)

    def test_opt_in_generates_player_baseline(self):
        report = analyze_matchup(
            "BUF", "MIA", self.pool, trials=5000,
            allow_depth_chart_first=True,
        )
        self.assertEqual(report["eligible_players"], 1)
        self.assertEqual(report["players"][0]["props"][2]["recent_per_game_baseline"], 72.0)

    def test_priced_prop_gets_simulated_probability(self):
        lines = {"BUF:Example Receiver:receiving_yards": 69.5}
        report = analyze_matchup(
            "BUF", "MIA", self.pool, prop_lines=lines,
            trials=5000, allow_depth_chart_first=True,
        )
        sim = report["players"][0]["props"][2]["simulation"]
        self.assertAlmostEqual(
            sim["over_probability"] + sim["under_probability"]
            + sim["push_probability"], 100.0, places=2
        )

    def test_invalid_same_team_matchup_rejected(self):
        with self.assertRaises(ValueError):
            analyze_matchup("BUF", "BUF", self.pool)


if __name__ == "__main__":
    unittest.main()
