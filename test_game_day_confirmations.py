import unittest
from datetime import datetime, timezone

from game_day_confirmations import validate_team_market_confirmation


class TeamMarketConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "source": "Official team game-day report",
            "source_url": "https://www.example.com/official-inactives",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "all_inactives_reviewed": True,
            "players": [
                {"name": f"{team} Starter {i}", "team": team,
                 "status": "active", "starter": True}
                for team in ("BUF", "MIA") for i in range(22)
            ],
        }

    def test_full_fresh_official_confirmation_passes(self):
        valid, reason = validate_team_market_confirmation(self.payload, "BUF", "MIA")
        self.assertTrue(valid)
        self.assertIn("22 confirmed", reason)

    def test_missing_full_inactive_review_blocks(self):
        payload = dict(self.payload, all_inactives_reviewed=False)
        valid, reason = validate_team_market_confirmation(payload, "BUF", "MIA")
        self.assertFalse(valid)
        self.assertIn("all_inactives_reviewed", reason)

    def test_incomplete_starter_list_blocks(self):
        payload = dict(self.payload)
        payload["players"] = payload["players"][:-1]
        valid, reason = validate_team_market_confirmation(payload, "BUF", "MIA")
        self.assertFalse(valid)
        self.assertIn("are required", reason)


if __name__ == "__main__":
    unittest.main()
