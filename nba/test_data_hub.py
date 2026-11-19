import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from nba.data_hub import build_report


class TestNBADataHub(unittest.TestCase):
    def test_missing_lineups_and_odds_keep_status_simulation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "stats.json"
            stats.write_text(json.dumps({"league": "NBA"}), encoding="utf-8")
            with (
                patch("nba.data_hub.validate_payload", return_value={"ready": True, "warnings": []}),
                patch("nba.data_hub.build_context", return_value={
                    "event": {"event_id": "123"}, "source": "ESPN", "retrieved_at": "2026-11-12T12:00:00Z",
                    "home_rest_days": 2, "away_rest_days": 1, "warnings": []
                }),
                patch("nba.data_hub.fetch_official_injuries", return_value={
                    "source": "NBA official injury report", "retrieved_at": "2026-11-12T12:00:00Z",
                    "report_url": "https://official.nba.com/report.pdf", "player_statuses": [],
                    "team_submission": {}, "warnings": []
                }),
                patch("nba.data_hub.fetch_espn_bet_odds", side_effect=RuntimeError("not posted")),
                patch.dict(os.environ, {"ODDS_API_KEY": ""}),
            ):
                report = build_report("WAS", "DET", date(2026, 11, 12), str(stats))
        self.assertEqual(report["overall_status"], "simulation_only_missing_inputs")
        self.assertFalse(report["readiness"]["confirmed_lineups"])
        self.assertFalse(report["readiness"]["two_sided_odds"])
        self.assertFalse(report["readiness"]["bet_eligible_data"])

    def test_standard_team_aliases_normalize_for_official_and_lineup_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "stats.json"
            stats.write_text(json.dumps({"league": "NBA"}), encoding="utf-8")
            lineup = Path(tmp) / "lineup.json"
            lineup.write_text(json.dumps({"source": "official team lineup", "confirmed_at": "2026-11-12T12:00:00Z", "teams": {
                code: {f"Player {i}": {"starter": True, "confirmed": True, "status": "available", "minutes": 30, "minutes_sd": 2}
                       for i in range(5)} for code in ("GS", "TOR")
            }}), encoding="utf-8")
            with (
                patch("nba.data_hub.validate_payload", return_value={"ready": True, "warnings": []}),
                patch("nba.data_hub.build_context", return_value={
                    "event": {"event_id": "123"}, "source": "ESPN", "retrieved_at": "2026-11-12T12:00:00Z",
                    "home_rest_days": 2, "away_rest_days": 1, "warnings": []
                }),
                patch("nba.data_hub.fetch_official_injuries", return_value={
                    "source": "NBA official injury report", "retrieved_at": "2026-11-12T12:00:00Z",
                    "report_url": "https://official.nba.com/report.pdf", "player_statuses": [],
                    "team_submission": {"GS": "SUBMITTED", "TOR": "SUBMITTED"}, "warnings": []
                }),
                patch("nba.data_hub.validate_game_availability", return_value=(True, "valid")),
                patch("nba.data_hub.fetch_roster", side_effect=[
                    [{"name": f"Player {i}"} for i in range(5)],
                    [{"name": f"Player {i}"} for i in range(5)],
                ]),
                patch("nba.data_hub.fetch_espn_bet_odds", side_effect=RuntimeError("not posted")),
                patch.dict(os.environ, {"ODDS_API_KEY": ""}),
            ):
                report = build_report("GSW", "TOR", date(2026, 11, 12), str(stats), str(lineup))
        self.assertTrue(report["readiness"]["official_injuries"])
        self.assertTrue(report["readiness"]["confirmed_lineups"])

    def test_espn_bet_two_sided_timestamped_odds_can_satisfy_odds_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "stats.json"
            stats.write_text(json.dumps({"league": "NBA"}), encoding="utf-8")
            with (
                patch("nba.data_hub.validate_payload", return_value={"ready": True, "warnings": []}),
                patch("nba.data_hub.build_context", return_value={
                    "event": {"event_id": "123"}, "source": "ESPN", "retrieved_at": "2026-11-12T12:00:00Z",
                    "home_rest_days": 2, "away_rest_days": 1, "warnings": []
                }),
                patch("nba.data_hub.fetch_official_injuries", return_value={
                    "source": "NBA official injury report", "retrieved_at": "2026-11-12T12:00:00Z",
                    "report_url": "https://official.nba.com/report.pdf", "player_statuses": [],
                    "team_submission": {}, "warnings": []
                }),
                patch("nba.data_hub.fetch_espn_bet_odds", return_value={
                    "home_ml_odds": -115, "away_ml_odds": 105,
                    "home_spread": -2.5, "home_spread_odds": -110, "away_spread_odds": -110,
                    "total": 221.5, "over_odds": -110, "under_odds": -110,
                    "last_updated": "2026-11-12T11:59:00Z",
                    "retrieved_at": "2026-11-12T12:00:00Z",
                    "source": "ESPN BET via ESPN Core API",
                }),
                patch.dict(os.environ, {"ODDS_API_KEY": ""}),
            ):
                report = build_report("WAS", "DET", date(2026, 11, 12), str(stats))
        self.assertTrue(report["readiness"]["two_sided_odds"])
        self.assertTrue(report["readiness"]["espn_bet_moneyline"])
        self.assertTrue(report["readiness"]["espn_bet_spread"])
        self.assertTrue(report["readiness"]["espn_bet_total"])
        self.assertEqual(report["sources"]["sportsbook_odds"]["provider"], "ESPN BET via ESPN Core API")

    def test_espn_bet_without_quote_timestamp_does_not_satisfy_odds_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "stats.json"
            stats.write_text(json.dumps({"league": "NBA"}), encoding="utf-8")
            with (
                patch("nba.data_hub.validate_payload", return_value={"ready": True, "warnings": []}),
                patch("nba.data_hub.build_context", return_value={
                    "event": {"event_id": "123"}, "source": "ESPN", "retrieved_at": "2026-11-12T12:00:00Z",
                    "home_rest_days": 2, "away_rest_days": 1, "warnings": []
                }),
                patch("nba.data_hub.fetch_official_injuries", return_value={
                    "source": "NBA official injury report", "retrieved_at": "2026-11-12T12:00:00Z",
                    "report_url": "https://official.nba.com/report.pdf", "player_statuses": [],
                    "team_submission": {}, "warnings": []
                }),
                patch("nba.data_hub.fetch_espn_bet_odds", return_value={
                    "home_ml_odds": -115, "away_ml_odds": 105,
                    "retrieved_at": "2026-11-12T12:00:00Z",
                    "source": "ESPN BET via ESPN Core API",
                }),
                patch.dict(os.environ, {"ODDS_API_KEY": ""}),
            ):
                report = build_report("WAS", "DET", date(2026, 11, 12), str(stats))
        self.assertFalse(report["readiness"]["two_sided_odds"])
        self.assertFalse(report["readiness"]["espn_bet_moneyline"])

    def test_injury_roster_mismatch_blocks_official_injury_readiness(self):
        from nba.data_hub import validate_injury_roster_consistency
        statuses = [{"team": "MEM", "player": "Wrong Team Player", "status": "Out"}]
        with patch("nba.data_hub.fetch_roster", side_effect=[
            [{"name": "Memphis Player"}], [{"name": "Washington Player"}]
        ]):
            result = validate_injury_roster_consistency(statuses, ("MEM", "WSH"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["mismatches"][0]["player"], "Wrong Team Player")

    def test_quarantines_player_team_mismatches_from_trusted_injury_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "stats.json"
            stats.write_text(json.dumps({"league": "NBA"}), encoding="utf-8")
            with (
                patch("nba.data_hub.validate_payload", return_value={"ready": True, "warnings": []}),
                patch("nba.data_hub.build_context", return_value={
                    "event": {"event_id": "123"}, "source": "ESPN",
                    "retrieved_at": "2026-11-19T12:00:00Z",
                    "home_rest_days": 2, "away_rest_days": 1, "warnings": []
                }),
                patch("nba.data_hub.fetch_official_injuries", return_value={
                    "source": "NBA official injury report",
                    "retrieved_at": "2026-11-19T12:00:00Z",
                    "report_url": "https://official.nba.com/report.pdf",
                    "player_statuses": [
                        {"team": "GS", "player": "Jimmy Butler III", "status": "Out"},
                        {"team": "GS", "player": "Anthony Edwards", "status": "Out"},
                    ],
                    "team_submission": {"GS": "SUBMITTED", "MEM": "SUBMITTED"},
                    "warnings": []
                }),
                patch("nba.data_hub.fetch_roster", side_effect=[
                    [{"name": "Ja Morant"}],
                    [{"name": "Jimmy Butler"}],
                ]),
                patch("nba.data_hub.fetch_espn_bet_odds", side_effect=RuntimeError("not posted")),
                patch.dict(os.environ, {"ODDS_API_KEY": ""}),
            ):
                report = build_report("MEM", "GSW", date(2026, 11, 19), str(stats))
        injuries = report["sources"]["injuries"]
        self.assertEqual(
            [(row["team"], row["player"]) for row in injuries["player_statuses"]],
            [("GS", "Jimmy Butler III")]
        )
        self.assertEqual(
            [(row["team"], row["player"]) for row in injuries["untrusted_player_statuses"]],
            [("GS", "Anthony Edwards")]
        )
        self.assertEqual(injuries["status"], "incomplete")
        self.assertFalse(report["readiness"]["injury_roster_consistent"])
        self.assertFalse(report["readiness"]["official_injuries"])

    def test_bad_team_codes_rejected(self):
        with self.assertRaisesRegex(ValueError, "recognized NBA"):
            build_report("XXX", "DET", date(2026, 11, 12))


if __name__ == "__main__":
    unittest.main()
