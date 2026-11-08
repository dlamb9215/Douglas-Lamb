import unittest
from datetime import date
from unittest.mock import patch

from nba.schedule import normalize_team, _event_row, build_context

class TestNBASchedule(unittest.TestCase):
    def test_standard_abbreviation_aliases(self):
        self.assertEqual(normalize_team("GSW"), "GS")
        self.assertEqual(normalize_team("NYK"), "NY")
        self.assertEqual(normalize_team("BOS"), "BOS")

    def test_parses_event_and_final_status(self):
        event = {
            "id": "123",
            "date": "2026-11-07T22:00Z",
            "competitions": [{
                "date": "2026-11-07T22:00Z",
                "status": {"type": {"state": "post", "completed": True}},
                "venue": {"fullName": "Example Arena", "address": {"city": "Boston"}},
                "competitors": [
                    {"homeAway": "home", "score": "110", "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
                    {"homeAway": "away", "score": "105", "team": {"abbreviation": "NYK", "displayName": "New York Knicks"}},
                ],
            }],
        }
        row = _event_row(event)
        self.assertEqual(row["event_id"], "123")
        self.assertTrue(row["completed"])
        self.assertEqual(row["home"]["score"], 110.0)
        self.assertEqual(row["venue_city"], "Boston")

    def test_context_calculates_rest_and_does_not_invent_travel(self):
        def row(day, home, away, completed=True):
            return {
                "event_id": day + home, "date": day, "start_time": day + "T23:00:00+00:00",
                "home": {"abbreviation": home}, "away": {"abbreviation": away},
                "completed": completed, "status": "post" if completed else "pre",
                "venue": None, "venue_city": None,
            }
        dates = {
            date(2026, 11, 5): [row("2026-11-05", "BOS", "MIA")],
            date(2026, 11, 6): [row("2026-11-06", "NY", "ATL")],
            date(2026, 11, 7): [row("2026-11-07", "BOS", "NY")],
            date(2026, 11, 8): [row("2026-11-08", "BOS", "NY", False)],
        }
        with patch("nba.schedule.fetch_scoreboard", side_effect=lambda d: dates.get(d, [])):
            with patch("nba.schedule.time.sleep"):
                result = build_context("BOS", "NYK", date(2026, 11, 8), lookback_days=3)
        self.assertEqual(result["home_rest_days"], 2)
        self.assertEqual(result["away_rest_days"], 1)
        self.assertIsNone(result["home_travel_miles"])
        self.assertTrue(result["warnings"])

    def test_rejects_missing_or_ambiguous_matchup(self):
        with patch("nba.schedule.fetch_scoreboard", return_value=[]):
            with patch("nba.schedule.time.sleep"):
                with self.assertRaisesRegex(ValueError, "found 0"):
                    build_context("BOS", "NYK", date(2026, 11, 8), lookback_days=1)

if __name__ == "__main__":
    unittest.main()
