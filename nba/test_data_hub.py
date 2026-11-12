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

    def test_bad_team_codes_rejected(self):
        with self.assertRaisesRegex(ValueError, "recognized NBA"):
            build_report("XXX", "DET", date(2026, 11, 12))


if __name__ == "__main__":
    unittest.main()
