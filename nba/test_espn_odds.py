import unittest
from unittest.mock import patch

from nba.espn_odds import (
    ESPN_BET_PROVIDER_ID, _resolve_odds_rows, parse_espn_bet_row, fetch_espn_bet_odds
)


class TestESPNBETOdds(unittest.TestCase):
    def test_only_selects_espn_bet_provider(self):
        payload = {"items": [
            {"provider_id": 37, "provider_name": "FanDuel"},
            {"provider_id": ESPN_BET_PROVIDER_ID, "provider_name": "ESPN BET"},
        ]}
        rows = _resolve_odds_rows("123", payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider_name"], "ESPN BET")

    def test_normalizes_current_and_opening_lines(self):
        row = {
            "provider_id": 68, "provider_name": "ESPN BET",
            "home_team_odds_current_money_line_american": "-155",
            "away_team_odds_current_money_line_american": "+135",
            "home_team_odds_current_spread_value": "-4.5",
            "home_team_odds_spread_odds": "-110",
            "away_team_odds_spread_odds": "-110",
            "current_total_value": "221.5",
            "current_over_american": "-108",
            "current_under_american": "-112",
            "home_team_odds_open_spread_value": "-3.5",
            "open_total_value": "219.5",
            "home_team_odds_open_money_line_american": "-145",
            "away_team_odds_open_money_line_american": "+125",
        }
        result = parse_espn_bet_row(row)
        self.assertEqual(result["home_ml_odds"], -155)
        self.assertEqual(result["away_ml_odds"], 135)
        self.assertEqual(result["home_spread"], -4.5)
        self.assertEqual(result["away_spread"], 4.5)
        self.assertEqual(result["total"], 221.5)
        self.assertEqual(result["opening_home_spread"], -3.5)
        self.assertEqual(result["opening_total"], 219.5)

    def test_missing_espn_bet_market_is_explicit(self):
        with patch("nba.espn_odds._get_json", return_value={"items": [
            {"provider_id": 37, "provider_name": "FanDuel"}
        ]}):
            with self.assertRaisesRegex(RuntimeError, "no other sportsbook was substituted"):
                fetch_espn_bet_odds("123")

    def test_fetch_uses_event_odds_endpoint(self):
        row = {"provider_id": 68, "provider_name": "ESPN BET",
               "home_team_odds_current_money_line_american": "-120",
               "away_team_odds_current_money_line_american": "+100"}
        with patch("nba.espn_odds._get_json", return_value={"items": [row]}) as mocked:
            result = fetch_espn_bet_odds("401234567")
        self.assertIn("/events/401234567/competitions/401234567/odds", mocked.call_args.args[0])
        self.assertEqual(result["home_ml_odds"], -120)
        self.assertEqual(result["source"], "ESPN BET via ESPN Core API")


if __name__ == "__main__":
    unittest.main()
