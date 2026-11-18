import unittest
from datetime import datetime, timezone, timedelta

from nhl.readiness import validate_confirmed_goalies


class NHLReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
        self.payload = {
            "confirmed": True, "home": "DAL", "away": "FLA",
            "source_url": "https://www.nhl.com/",
            "checked_at_utc": (self.now - timedelta(minutes=20)).isoformat(),
            "goalies": {
                "home": {"team": "DAL", "player_id": 1001, "status": "confirmed_starter"},
                "away": {"team": "FLA", "player_id": 2002, "status": "confirmed_starter"},
            },
        }

    def test_accepts_fresh_confirmed_matchup_goalies(self):
        result = validate_confirmed_goalies(self.payload, "DAL", "FLA", now=self.now)
        self.assertTrue(result["availability_confirmed"])
        self.assertEqual(result["goalies"]["home"]["player_id"], 1001)

    def test_rejects_projected_goalie(self):
        self.payload["goalies"]["home"]["status"] = "projected"
        with self.assertRaises(ValueError):
            validate_confirmed_goalies(self.payload, "DAL", "FLA", now=self.now)

    def test_rejects_wrong_matchup(self):
        with self.assertRaises(ValueError):
            validate_confirmed_goalies(self.payload, "COL", "FLA", now=self.now)

    def test_rejects_stale_confirmation(self):
        self.payload["checked_at_utc"] = (self.now - timedelta(hours=4)).isoformat()
        with self.assertRaises(ValueError):
            validate_confirmed_goalies(self.payload, "DAL", "FLA", now=self.now)

    def test_rejects_nonofficial_source_and_missing_goalie(self):
        self.payload["source_url"] = "http://example.com"
        with self.assertRaises(ValueError):
            validate_confirmed_goalies(self.payload, "DAL", "FLA", now=self.now)
        self.payload["source_url"] = "https://www.nhl.com/"
        self.payload["goalies"]["away"]["player_id"] = None
        with self.assertRaises(ValueError):
            validate_confirmed_goalies(self.payload, "DAL", "FLA", now=self.now)


if __name__ == "__main__":
    unittest.main()
