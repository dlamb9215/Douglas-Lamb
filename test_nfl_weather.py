import unittest
from unittest.mock import patch
from nfl_weather import fetch_matchup_weather


class NFLWeatherTests(unittest.TestCase):
    @patch("nfl_weather._get_json")
    @patch("nfl_weather._get_rows")
    def test_fetches_venue_weather_for_scheduled_match(self, rows, get_json):
        rows.return_value = [{
            "home_team":"BUF","away_team":"MIA","season":"2026","week":"9",
            "game_type":"REG","gameday":"2026-11-08","gametime":"13:00",
            "stadium":"Highmark Stadium","location":"Orchard Park, NY",
            "roof":"outdoors","surface":"grass"
        }]
        get_json.side_effect = [
            {"results":[{"country_code":"US","latitude":42.77,"longitude":-78.78}]},
            {"hourly":{
                "time":["2026-11-08T17:00","2026-11-08T18:00"],
                "temperature_2m":[5,4],"precipitation":[0.2,0.1],
                "wind_speed_10m":[30,25],"wind_gusts_10m":[45,40]
            }}
        ]
        result = fetch_matchup_weather("BUF","MIA",2026,9)
        self.assertTrue(result["available"])
        self.assertEqual(result["venue"],"Highmark Stadium")
        self.assertEqual(result["wind_mph"],18.6)
        self.assertEqual(result["weather_exposure"],"OUTDOOR_OR_UNKNOWN")

    @patch("nfl_weather._get_rows", return_value=[])
    def test_missing_game_fails_closed(self, rows):
        with self.assertRaises(RuntimeError):
            fetch_matchup_weather("BUF","MIA",2026,9)


if __name__ == "__main__":
    unittest.main()
