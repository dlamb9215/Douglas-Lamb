import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ncaa.players import load_player_inputs, simulate_player, simulate_players


class PlayerProjectionTests(unittest.TestCase):
    def setUp(self):
        self.player = {
            "player": "Test Runner",
            "team": "Test U",
            "role": "RB",
            "expected_opportunities": 18,
            "success_probability": 1.0,
            "yards_per_success": 4.8,
            "yards_sd_per_success": 2.1,
            "touchdown_rate_per_opportunity": 0.04,
            "source": "test fixture",
            "as_of": date.today().isoformat(),
            "prop_lines": {"yards": 70.5, "opportunities": 17.5},
        }

    def test_projection_reproducible_and_has_market_probabilities(self):
        a = simulate_player(self.player, trials=2500, seed=7,
                            prop_lines=self.player["prop_lines"])
        b = simulate_player(self.player, trials=2500, seed=7,
                            prop_lines=self.player["prop_lines"])
        self.assertEqual(a, b)
        self.assertIn("yards", a["prop_probabilities"])
        self.assertAlmostEqual(
            a["prop_probabilities"]["yards"]["over_probability"] +
            a["prop_probabilities"]["yards"]["under_probability"] +
            a["prop_probabilities"]["yards"]["push_probability"], 1.0
        )

    def test_input_requires_provenance_and_fresh_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "players.json"
            path.write_text(json.dumps([self.player]))
            self.assertEqual(len(load_player_inputs(path)), 1)
            old = dict(self.player, as_of="2020-01-01")
            path.write_text(json.dumps([old]))
            with self.assertRaisesRegex(ValueError, "days old"):
                load_player_inputs(path)

    def test_cli_player_file_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "players.json"
            path.write_text(json.dumps([self.player]))
            result = simulate_players(path, trials=500, seed=9)
            self.assertEqual(result[0]["player"], "Test Runner")

    def test_invalid_role_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "players.json"
            path.write_text(json.dumps([dict(self.player, role="K")]))
            with self.assertRaisesRegex(ValueError, "role"):
                load_player_inputs(path)


if __name__ == "__main__":
    unittest.main()
