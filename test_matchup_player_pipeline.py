import unittest
from datetime import datetime, timezone
from game_day_confirmations import validate_confirmation_file, confirmed_player_copy
from matchup_player_pipeline import analyze_matchup


class TestGameDayConfirmations(unittest.TestCase):
    def setUp(self):
        self.data = {
            "source": "official team inactive report",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "players": [{"name": "Example Receiver", "team": "BUF",
                         "status": "active", "starter": True}],
        }

    def test_fresh_active_starter_is_confirmed(self):
        confirmations = validate_confirmation_file(self.data)
        player = {"name": "Example Receiver", "team": "BUF",
                  "status": "unknown", "starter": False}
        confirmed = confirmed_player_copy(player, confirmations)
        self.assertTrue(confirmed["starter"])
        self.assertEqual(confirmed["status"], "active")

    def test_inactive_player_is_not_confirmed(self):
        self.data["players"][0]["status"] = "inactive"
        confirmations = validate_confirmation_file(self.data)
        player = {"name": "Example Receiver", "team": "BUF"}
        self.assertIsNone(confirmed_player_copy(player, confirmations))

    def test_stale_confirmation_rejected(self):
        self.data["checked_at_utc"] = "2020-01-01T00:00:00+00:00"
        with self.assertRaises(ValueError):
            validate_confirmation_file(self.data)

    def test_missing_source_rejected(self):
        del self.data["source"]
        with self.assertRaises(ValueError):
            validate_confirmation_file(self.data)


class TestMatchupPlayerPipeline(unittest.TestCase):
    def setUp(self):
        self.pool = {
            "source": "test-fixture",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "season": 2026, "last_n_weeks": 5,
            "players": [{
                "name": "Example Receiver", "team": "BUF", "position": "WR",
                "status": "active", "starter": True, "games": 5,
                "targets_per_game": 8.0, "receptions_per_game": 6.0,
                "receiving_yards_per_game": 72.0, "receiving_tds_per_game": 0.4,
                "offense_snaps_per_game": 55.0, "offense_snap_pct_avg": 80.0,
            }]
        }
        self.confirmations = {
            ("BUF", "example receiver"): {
                "status": "active", "starter": True, "note": "official inactive report"
            }
        }

    def test_unconfirmed_players_are_blocked_by_default(self):
        report = analyze_matchup("BUF", "MIA", self.pool)
        self.assertEqual(report["eligible_players"], 0)
        self.assertEqual(len(report["blocked_players"]), 1)

    def test_confirmed_player_gets_recent_baseline(self):
        report = analyze_matchup("BUF", "MIA", self.pool,
                                 trials=5000, confirmations=self.confirmations)
        self.assertEqual(report["eligible_players"], 1)
        self.assertEqual(report["players"][0]["props"][2]["recent_per_game_baseline"], 72.0)

    def test_priced_prop_runs_reproducible_trial_set(self):
        lines = {"BUF:Example Receiver:receiving_yards": 69.5}
        a = analyze_matchup("BUF", "MIA", self.pool, lines, 5000, 77, self.confirmations)
        b = analyze_matchup("BUF", "MIA", self.pool, lines, 5000, 77, self.confirmations)
        sim = a["players"][0]["props"][2]["simulation"]
        self.assertEqual(sim, b["players"][0]["props"][2]["simulation"])
        self.assertEqual(sim["trials"], 5000)
        self.assertAlmostEqual(sim["over_probability"] + sim["under_probability"]
                               + sim["push_probability"], 100.0, places=2)

    def test_invalid_same_team_matchup_rejected(self):
        with self.assertRaises(ValueError):
            analyze_matchup("BUF", "BUF", self.pool, confirmations=self.confirmations)


if __name__ == "__main__":
    unittest.main()
