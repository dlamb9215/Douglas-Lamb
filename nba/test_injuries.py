import unittest

from nba.injuries import parse_report_text, latest_report_url
from datetime import date
from unittest.mock import patch

class TestNBAOfficialInjuries(unittest.TestCase):
    def test_parses_official_report_player_statuses_and_teams(self):
        sample = """Injury Report: 11/07/26 11:15 PM
Page 1 of 8
11/07/2026 05:00 (ET) DEN@IND Denver Nuggets DeRozan, DeMar Available Injury/Illness - Low Back Spasms
Strawther, Julian Out Injury/Illness - Left Knee Sprain
Indiana Pacers Furphy, Johnny Out Injury/Illness - Right ACL Repair
11/08/2026 08:00 (ET) NYK@CLE New York Knicks Hart, Josh Out Injury/Illness - Right Ankle Soreness
Cleveland Cavaliers Allen, Jarrett Out Injury/Illness - Right Knee Contusion
"""
        result = parse_report_text(sample, {"DEN", "IND"})
        self.assertEqual(len(result["players"]), 3)
        self.assertEqual(result["players"][0]["player"], "DeMar DeRozan")
        self.assertEqual(result["players"][0]["team"], "DEN")
        self.assertEqual(result["players"][0]["status"], "Available")
        self.assertEqual(result["players"][1]["status"], "Out")
        self.assertEqual({row["team"] for row in result["players"]}, {"DEN", "IND"})

    def test_flags_team_not_yet_submitted(self):
        result = parse_report_text("Brooklyn Nets NOT YET SUBMITTED", {"BKN"})
        self.assertEqual(result["team_submission"]["BKN"], "NOT YET SUBMITTED")

    def test_selects_latest_report_not_after_game_date(self):
        html = """<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-07_10_45PM.pdf">old</a>
        <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-08_08_00AM.pdf">new</a>"""
        with patch("nba.injuries._get", return_value=html.encode()):
            url = latest_report_url(date(2026, 11, 8), 2027)
        self.assertIn("2026-11-08_08_00AM", url)

    def test_rejects_stale_report(self):
        html = """<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-05_10_45PM.pdf">old</a>"""
        with patch("nba.injuries._get", return_value=html.encode()):
            with self.assertRaisesRegex(RuntimeError, "No NBA official injury-report PDF"):
                latest_report_url(date(2026, 11, 8), 2027)

if __name__ == "__main__":
    unittest.main()
