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
            {"results":[{"country_code":"US","name":"Orchard Park","admin1":"New York",
                         "country":"United States","latitude":42.77,"longitude":-78.78}]},
            {"hourly":{
                "time":["2026-11-08T17:00","2026-11-08T18:00"],
                "temperature_2m":[5,4],"precipitation":[0.2,0.1],
                "wind_speed_10m":[30,25],"wind_gusts_10m":[45,40]
            }}
        ]
        result = fetch_matchup_weather("BUF","MIA",2026,9)
        self.assertTrue(result["available"])
        self.assertEqual(result["venue"],"Highmark Stadium")
        self.assertEqual(result["country_code"],"US")
        self.assertEqual(result["wind_mph"],15.5)
        self.assertEqual(result["weather_exposure"],"OUTDOOR_OR_UNKNOWN")

    @patch("nfl_weather._get_json")
    @patch("nfl_weather._get_rows")
    def test_neutral_bernabeu_game_uses_madrid_not_us_geocoder_result(self, rows, get_json):
        rows.return_value = [{
            "home_team":"ATL","away_team":"CIN","season":"2026","week":"9",
            "game_type":"REG","gameday":"2026-11-08","gametime":"09:30",
            "stadium":"Bernabeu","location":"Neutral",
            "roof":"","surface":"fieldturf"
        }]
        get_json.side_effect = [
            {"results":[
                {"country_code":"US","name":"Joplin","admin1":"Missouri",
                 "country":"United States","latitude":37.10,"longitude":-94.79},
                {"country_code":"ES","name":"Madrid","admin1":"Madrid",
                 "country":"Spain","latitude":40.45,"longitude":-3.69}
            ]},
            {"hourly":{
                "time":["2026-11-08T14:00","2026-11-08T15:00"],
                "temperature_2m":[12,13],"precipitation":[0,0],
                "wind_speed_10m":[10,11],"wind_gusts_10m":[15,16]
            }}
        ]
        result = fetch_matchup_weather("ATL","CIN",2026,9)
        self.assertEqual(result["country_code"],"ES")
        self.assertEqual(result["venue_city"],"Madrid, Spain")
        self.assertAlmostEqual(result["latitude"],40.45)
        self.assertAlmostEqual(result["longitude"],-3.69)

    @patch("nfl_weather._get_json", return_value={"results":[
        {"country_code":"US","name":"Joplin","admin1":"Missouri",
         "country":"United States","latitude":37.10,"longitude":-94.79}
    ]})
    @patch("nfl_weather._get_rows")
    def test_wrong_country_geocoder_result_fails_closed(self, rows, get_json):
        rows.return_value = [{
            "home_team":"ATL","away_team":"CIN","season":"2026","week":"9",
            "game_type":"REG","gameday":"2026-11-08","gametime":"09:30",
            "stadium":"Bernabeu","location":"Neutral"
        }]
        with self.assertRaisesRegex(RuntimeError, "expected country ES"):
            fetch_matchup_weather("ATL","CIN",2026,9)

    @patch("nfl_weather._get_rows", return_value=[])
    def test_missing_game_fails_closed(self, rows):
        with self.assertRaises(RuntimeError):
            fetch_matchup_weather("BUF","MIA",2026,9)


if __name__ == "__main__":
    unittest.main()
