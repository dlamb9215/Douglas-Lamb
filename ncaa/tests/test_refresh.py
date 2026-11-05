import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ncaa.data.refresh import extract_stats, parse_advanced, write_outputs


class RefreshTests(unittest.TestCase):
    def test_extract_stats_normalizes_categories(self):
        result = extract_stats({"stats": [
            {"category": "passingYards", "stat": "312"},
            {"category": "totalYards", "stat": "450"},
        ]})
        self.assertEqual(result["passingyards"], 312.0)
        self.assertEqual(result["totalyards"], 450.0)

    def test_advanced_rows_accept_nested_metrics(self):
        result = parse_advanced([{
            "team": "Example U",
            "offense": {"successRate": 0.47},
            "defense": {"successRate": 0.39},
        }])
        self.assertEqual(result["example u"]["offense"]["successRate"], 0.47)

    def test_outputs_write_csv_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            profiles = [{
                "team": "Example U", "points_for": 30, "points_against": 20,
                "yards_per_play": 6.0, "yards_per_play_allowed": 5.0,
                "plays_per_game": 70, "points_per_drive": "",
                "turnovers_per_game": 1.0, "takeaways_per_game": 1.5,
                "explosive_play_rate": .12, "success_rate": .42,
                "strength_rating": 0, "games_sampled": 4,
                "source": "test", "as_of": "2026-11-04",
            }]
            write_outputs(profiles, {"Example U": {"games": 4}},
                          {"year": 2026}, Path(tmp))
            self.assertTrue((Path(tmp) / "team_profiles.csv").exists())
            data = json.loads((Path(tmp) / "team_rankings.json").read_text())
            self.assertIn("Example U", data["teams"])


if __name__ == "__main__":
    unittest.main()
