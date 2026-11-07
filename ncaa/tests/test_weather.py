import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from ncaa.weather import fetch_game_weather


class WeatherContextTests(unittest.TestCase):
    def test_fetches_near_kickoff_weather_and_converts_units(self):
        kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        iso = kickoff.isoformat()
        games = [{"homeTeam": "Home U", "awayTeam": "Away U",
                  "startDate": iso, "venueId": 12}]
        venues = [{"id": 12, "name": "Stadium", "latitude": 40.0, "longitude": -75.0}]
        forecast = {"hourly": {
            "time": [kickoff.replace(minute=0).replace(tzinfo=None).isoformat()],
            "temperature_2m": [10],
            "precipitation": [1.2],
            "wind_speed_10m": [16.0934],
            "wind_gusts_10m": [32.1868],
        }}
        with patch("ncaa.weather.api_get", side_effect=[games, venues]), \
             patch("ncaa.weather._get_open_meteo", return_value=forecast):
            result = fetch_game_weather(2026, "Home U", "Away U", "test-key")
        self.assertTrue(result["available"])
        self.assertEqual(result["temperature_f"], 50.0)
        self.assertEqual(result["wind_mph"], 10.0)
        self.assertEqual(result["wind_gust_mph"], 20.0)
        self.assertIn("not applied", result["model_treatment"])

    def test_missing_forecast_keeps_schedule_kickoff(self):
        kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        game = [{"homeTeam": "Home U", "awayTeam": "Away U",
                 "startDate": kickoff.isoformat(), "venueId": 12}]
        venues = [{"id": 12, "name": "Stadium", "latitude": 40.0, "longitude": -75.0}]
        with patch("ncaa.weather.api_get", side_effect=[game, venues]), \
             patch("ncaa.weather._get_open_meteo", side_effect=RuntimeError("forecast horizon unavailable")):
            result = fetch_game_weather(2026, "Home U", "Away U", "test-key")
        self.assertFalse(result["available"])
        self.assertEqual(result["kickoff"], kickoff.isoformat())
        self.assertIn("forecast horizon unavailable", result["weather_warning"])

    def test_missing_scheduled_match_is_not_guessed(self):
        with patch("ncaa.weather.api_get", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "No matching scheduled game"):
                fetch_game_weather(2026, "Home U", "Away U", "test-key")


if __name__ == "__main__":
    unittest.main()
