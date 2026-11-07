import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from game_day_confirmations import validate_confirmation_file, confirmed_player_copy
from matchup_player_pipeline import analyze_matchup, load_prop_lines


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

    def test_prop_line_file_requires_fresh_source_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lines.json"
            payload = {
                "source":"Example Sportsbook",
                "checked_at_utc":datetime.now(timezone.utc).isoformat(),
                "props":{"BUF:Example Receiver:receiving_yards":{
                    "line":69.5,"over_odds":-110,"under_odds":-110
                }}
            }
            path.write_text(json.dumps(payload),encoding="utf-8")
            props, metadata = load_prop_lines(path)
            self.assertEqual(props["BUF:Example Receiver:receiving_yards"]["line"],69.5)
            self.assertEqual(metadata["source"],"Example Sportsbook")

    def test_unconfirmed_players_are_blocked_by_default(self):
        report = analyze_matchup("BUF", "MIA", self.pool)
        self.assertEqual(report["eligible_players"], 0)
        self.assertEqual(len(report["blocked_players"]), 1)

    def test_confirmed_player_gets_recent_baseline(self):
        report = analyze_matchup("BUF", "MIA", self.pool,
                                 trials=5000, confirmations=self.confirmations)
        self.assertEqual(report["eligible_players"], 1)
        self.assertEqual(report["players"][0]["props"][2]["opponent_adjusted_projection"], 72.0)

    def test_priced_prop_runs_reproducible_trial_set(self):
        lines = {"BUF:Example Receiver:receiving_yards": 69.5}
        a = analyze_matchup("BUF", "MIA", self.pool, lines, 5000, 77, self.confirmations)
        b = analyze_matchup("BUF", "MIA", self.pool, lines, 5000, 77, self.confirmations)
        sim = a["players"][0]["props"][2]["simulation"]
        self.assertEqual(sim, b["players"][0]["props"][2]["simulation"])
        self.assertEqual(sim["trials"], 5000)
        self.assertAlmostEqual(sim["over_probability"] + sim["under_probability"]
                               + sim["push_probability"], 100.0, places=2)

    def test_recent_player_baseline_is_adjusted_for_opponent_defense(self):
        team_records = [
            {"team":"BUF","defense":{"passing":{"yards_per_game":200},"rushing":{"yards_per_game":100}}},
            {"team":"MIA","defense":{"passing":{"yards_per_game":250},"rushing":{"yards_per_game":150}}},
        ]
        report = analyze_matchup("BUF", "MIA", self.pool, trials=1000,
                                 confirmations=self.confirmations,
                                 team_records=team_records)
        projection = report["players"][0]
        self.assertGreater(projection["props"][2]["recent_per_game_baseline"], 72.0)
        self.assertTrue(projection["opponent_adjustment"]["applied"])
        self.assertEqual(projection["opponent_adjustment"]["opponent"], "MIA")

    def test_qb_passing_yards_uses_completions_times_opponent_yards_per_completion(self):
        pool = dict(self.pool)
        pool["players"] = list(self.pool["players"]) + [{
            "name":"Example QB","team":"BUF","position":"QB","status":"active",
            "starter":True,"games":5,"completions_per_game":25.0,
            "passing_yards_per_game":220.0,"passing_attempts_per_game":36.0,
            "passing_tds_per_game":1.5,"interceptions_per_game":0.5,
            "rushing_yards_per_game":12.0,"carries_per_game":2.0,
        }]
        confirmations = dict(self.confirmations)
        confirmations[("BUF","example qb")] = {
            "status":"active","starter":True,"note":"official team starter report"
        }
        team_records = [
            {"team":"BUF","defense":{"passing":{"yards_per_game":200,"completions_per_game":20},"rushing":{"yards_per_game":100}}},
            {"team":"MIA","defense":{"passing":{"yards_per_game":250,"completions_per_game":20},"rushing":{"yards_per_game":150}}},
        ]
        report = analyze_matchup("BUF","MIA",pool,trials=1000,
                                 confirmations=confirmations,team_records=team_records)
        qb = next(player for player in report["players"] if player["position"] == "QB")
        self.assertEqual(qb["props"][0]["opponent_adjusted_projection"],266.25)
        self.assertEqual(qb["opponent_adjustment"]["qb_completions_times_opponent_yards_per_completion"],312.5)

    def test_player_prop_market_comparison_removes_vig_and_reports_ev(self):
        lines = {"BUF:Example Receiver:receiving_yards": {
            "line": 69.5, "over_odds": -110, "under_odds": -110
        }}
        report = analyze_matchup("BUF", "MIA", self.pool, lines, 5000, 77,
                                 self.confirmations)
        market = report["players"][0]["props"][2]["market_comparison"]
        self.assertAlmostEqual(market["vig_free_over_probability"], 50.0, places=2)
        self.assertIn("over_expected_value_per_100", market)
        self.assertIn("under_edge_percentage_points", market)

    def test_invalid_same_team_matchup_rejected(self):
        with self.assertRaises(ValueError):
            analyze_matchup("BUF", "BUF", self.pool, confirmations=self.confirmations)


if __name__ == "__main__":
    unittest.main()
