import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ncaa.data.player_refresh import refresh_player_data


class PlayerRefreshTests(unittest.TestCase):
    def test_writes_player_stats_and_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("ncaa.data.player_refresh.api_get", side_effect=[
                [{"player": "Sample", "category": "rushing", "statType": "YDS", "stat": "100"}],
                [{"id": "1", "name": "Sample", "team": "Sample U", "usage": {"rush": 0.4}}],
                [{"id": "1", "firstName": "Sample", "lastName": "Player", "team": "Sample U", "position": "RB"}],
            ]):
                status = refresh_player_data(2026, "regular", "test-key", directory)
            self.assertTrue(status["stats_available"])
            self.assertTrue(status["usage_available"])
            self.assertTrue(status["roster_available"])
            payload = json.loads((Path(directory) / "player_season_data.json").read_text())
            self.assertEqual(payload["season_stats"][0]["player"], "Sample")
            self.assertEqual(payload["usage"][0]["usage"]["rush"], 0.4)
            self.assertEqual(payload["rosters"][0]["id"], "1")

    def test_provider_failure_preserves_previous_player_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "player_season_data.json"
            cache.write_text('{"preserve": true}')
            with patch("ncaa.data.player_refresh.api_get", side_effect=RuntimeError("CFBD returned 403")):
                status = refresh_player_data(2026, "regular", "test-key", directory)
            self.assertFalse(status["stats_available"])
            self.assertEqual(json.loads(cache.read_text()), {"preserve": True})
            self.assertTrue((Path(directory) / "player_data_status.json").exists())


if __name__ == "__main__":
    unittest.main()
