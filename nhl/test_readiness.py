import unittest
from datetime import datetime, timezone, timedelta

from nhl.readiness import validate_confirmed_goalies, validate_confirmed_skater_lineups


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

    def lineup_payload(self):
        return {
            "confirmed": True, "home": "DAL", "away": "FLA",
            "source_url": "https://www.nhl.com/",
            "checked_at_utc": (self.now - timedelta(minutes=20)).isoformat(),
            "lineups": {
                "home": {"team": "DAL", "player_ids": list(range(1, 19)), "scratched_player_ids": [90]},
                "away": {"team": "FLA", "player_ids": list(range(101, 119)), "scratched_player_ids": [190]},
            },
        }

    def test_accepts_fresh_confirmed_skater_lineups(self):
        out = validate_confirmed_skater_lineups(self.lineup_payload(), "DAL", "FLA", now=self.now)
        self.assertTrue(out["availability_confirmed"])
        self.assertEqual(len(out["lineups"]["home"]["player_ids"]), 18)

    def test_rejects_incomplete_or_duplicate_lineups(self):
        payload = self.lineup_payload()
        payload["lineups"]["home"]["player_ids"] = [1, 2, 3]
        with self.assertRaises(ValueError):
            validate_confirmed_skater_lineups(payload, "DAL", "FLA", now=self.now)
        payload = self.lineup_payload()
        payload["lineups"]["away"]["player_ids"][1] = payload["lineups"]["away"]["player_ids"][0]
        with self.assertRaises(ValueError):
            validate_confirmed_skater_lineups(payload, "DAL", "FLA", now=self.now)

    def test_rejects_scratch_marked_active_and_stale_lineup(self):
        payload = self.lineup_payload()
        payload["lineups"]["home"]["scratched_player_ids"] = [1]
        with self.assertRaises(ValueError):
            validate_confirmed_skater_lineups(payload, "DAL", "FLA", now=self.now)
        payload = self.lineup_payload()
        payload["checked_at_utc"] = (self.now - timedelta(hours=4)).isoformat()
        with self.assertRaises(ValueError):
            validate_confirmed_skater_lineups(payload, "DAL", "FLA", now=self.now)


if __name__ == "__main__":
    unittest.main()
