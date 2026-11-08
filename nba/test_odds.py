import unittest
from unittest.mock import patch

from nba.odds import matchup_odds, fetch_events

SAMPLE = [{
    "id": "event-1", "home_team": "Boston Celtics", "away_team": "New York Knicks",
    "commence_time": "2026-11-09T00:00:00Z",
    "bookmakers": [
        {"key": "book_a", "last_update": "2026-11-08T18:00:00Z", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Boston Celtics", "price": -150}, {"name": "New York Knicks", "price": 130}]},
            {"key": "spreads", "outcomes": [
                {"name": "Boston Celtics", "price": -110, "point": -4.5},
                {"name": "New York Knicks", "price": -110, "point": 4.5}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": -108, "point": 220.5},
                {"name": "Under", "price": -112, "point": 220.5}]},
        ]},
        {"key": "book_b", "last_update": "2026-11-08T18:01:00Z", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Boston Celtics", "price": -145}, {"name": "New York Knicks", "price": 135}]},
            {"key": "spreads", "outcomes": [
                {"name": "Boston Celtics", "price": -105, "point": -4.5},
                {"name": "New York Knicks", "price": -115, "point": 4.5}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": -110, "point": 221.5},
                {"name": "Under", "price": -110, "point": 221.5}]},
        ]},
    ],
}]

class TestNBAOdds(unittest.TestCase):
    def test_best_moneyline_and_consensus_lines(self):
        with patch("nba.odds.fetch_events", return_value=(SAMPLE, {"requests_remaining": "499"})):
            result = matchup_odds("Boston Celtics", "New York Knicks", "fake-key")
        self.assertEqual(result["home_ml_odds"], -145)
        self.assertEqual(result["away_ml_odds"], 135)
        self.assertEqual(result["home_spread"], -4.5)
        self.assertEqual(result["home_spread_odds"], -105)
        self.assertEqual(result["away_spread_odds"], -115)
        self.assertEqual(result["total"], 220.5)
        self.assertEqual(result["over_odds"], -108)
        self.assertEqual(result["under_odds"], -112)
        self.assertEqual(result["bookmaker_count"], 2)

    def test_requires_key(self):
        with self.assertRaisesRegex(RuntimeError, "ODDS_API_KEY"):
            fetch_events("")

    def test_requires_unique_match(self):
        with patch("nba.odds.fetch_events", return_value=([], {})):
            with self.assertRaisesRegex(RuntimeError, "found 0"):
                matchup_odds("Boston Celtics", "New York Knicks", "fake-key")

if __name__ == "__main__":
    unittest.main()
