import unittest
from datetime import datetime, timezone, timedelta
from market_data import validate_market_snapshot


class MarketSnapshotTests(unittest.TestCase):
    def test_no_market_is_allowed_without_source(self):
        result = validate_market_snapshot({"spread":None,"total":None})
        self.assertFalse(result["provided"])

    def test_fresh_timestamped_market_is_valid(self):
        now = datetime.now(timezone.utc)
        result = validate_market_snapshot(
            {"spread":-3.5,"total":48.5,"home_odds":150},
            "Example Sportsbook", now.isoformat(), now=now
        )
        self.assertTrue(result["provided"])
        self.assertEqual(result["lines"]["spread"],-3.5)

    def test_market_requires_source_and_timestamp(self):
        with self.assertRaises(ValueError):
            validate_market_snapshot({"total":48.5})

    def test_stale_market_is_rejected(self):
        now = datetime.now(timezone.utc)
        old = (now-timedelta(hours=7)).isoformat()
        with self.assertRaisesRegex(ValueError,"older"):
            validate_market_snapshot({"total":48.5},"Book",old,now=now)

    def test_zero_american_odds_are_rejected(self):
        now = datetime.now(timezone.utc)
        with self.assertRaisesRegex(ValueError,"cannot be zero"):
            validate_market_snapshot({"home_odds":0},"Book",now.isoformat(),now=now)


if __name__ == "__main__":
    unittest.main()
