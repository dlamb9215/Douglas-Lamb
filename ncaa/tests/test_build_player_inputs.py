import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ncaa.data.build_player_inputs import build_player_inputs


class BuildPlayerInputsTests(unittest.TestCase):
    def test_builds_position_specific_season_average_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player_path = root / "players.json"
            team_path = root / "teams.csv"
            output_path = root / "inputs.json"
            payload = {
                "metadata": {"retrieved_at": datetime.now(timezone.utc).isoformat()},
                "season_stats": [
                    {"player": "QB One", "team": "Sample U", "position": "QB",
                     "category": "passing", "statType": "ATT", "stat": "100"},
                    {"player": "QB One", "team": "Sample U", "position": "QB",
                     "category": "passing", "statType": "CMP", "stat": "65"},
                    {"player": "QB One", "team": "Sample U", "position": "QB",
                     "category": "passing", "statType": "YDS", "stat": "900"},
                    {"player": "QB One", "team": "Sample U", "position": "QB",
                     "category": "passing", "statType": "TD", "stat": "8"},
                    {"player": "RB One", "team": "Sample U", "position": "RB",
                     "category": "rushing", "statType": "CAR", "stat": "50"},
                    {"player": "RB One", "team": "Sample U", "position": "RB",
                     "category": "rushing", "statType": "YDS", "stat": "250"},
                ],
                "usage": [],
            }
            player_path.write_text(json.dumps(payload))
            with team_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["team", "games_sampled"])
                writer.writeheader()
                writer.writerow({"team": "Sample U", "games_sampled": 5})
            built = build_player_inputs(player_path, team_path, output_path)
            self.assertEqual(len(built), 2)
            qb = next(p for p in built if p["role"] == "QB")
            self.assertEqual(qb["expected_opportunities"], 20.0)
            self.assertEqual(qb["success_probability"], 0.65)
            rb = next(p for p in built if p["role"] == "RB")
            self.assertEqual(rb["expected_opportunities"], 10.0)
            self.assertEqual(rb["success_probability"], 1.0)
            self.assertTrue(output_path.exists())

    def test_current_roster_filter_excludes_non_roster_player(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player_path = root / "players.json"
            team_path = root / "teams.csv"
            output_path = root / "inputs.json"
            stats = []
            for pid, name, position, category, entries in [
                ("1", "QB One", "QB", "passing", [("ATT", 40), ("CMP", 25), ("YDS", 300), ("TD", 3)]),
                ("2", "QB Two", "QB", "passing", [("ATT", 20), ("CMP", 10), ("YDS", 100), ("TD", 1)]),
            ]:
                for stat_type, value in entries:
                    stats.append({"playerId": pid, "player": name, "team": "Sample U",
                                  "position": position, "category": category,
                                  "statType": stat_type, "stat": str(value)})
            player_path.write_text(json.dumps({
                "metadata": {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                             "roster_available": True},
                "season_stats": stats, "usage": [],
                "rosters": [{"id": "1", "firstName": "QB", "lastName": "One",
                             "team": "Sample U", "position": "QB"}],
            }))
            team_path.write_text("team,games_sampled\nSample U,4\n")
            built = build_player_inputs(player_path, team_path, output_path)
            self.assertEqual([p["player"] for p in built], ["QB One"])
            self.assertTrue(built[0]["roster_verified"])

    def test_player_team_filter_resolves_mascot_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player_path = root / "player_season_data.json"
            team_path = root / "team_profiles_fcs.csv"
            output_path = root / "inputs.json"
            ranking_path = root / "team_rankings_fcs.json"
            player_path.write_text(json.dumps({
                "metadata": {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                             "classification": "fcs", "roster_available": False},
                "season_stats": [
                    {"player": "Runner", "team": "Howard", "position": "RB",
                     "category": "rushing", "statType": "CAR", "stat": "40"},
                    {"player": "Runner", "team": "Howard", "position": "RB",
                     "category": "rushing", "statType": "YDS", "stat": "200"},
                ],
                "usage": [], "rosters": [],
            }))
            team_path.write_text("team,games_sampled\nHoward,4\n")
            ranking_path.write_text(json.dumps({
                "metadata": {"team_aliases": {"howard bison": "Howard"}},
                "teams": {},
            }))
            built = build_player_inputs(player_path, team_path, output_path,
                                        teams={"Howard Bison"}, classification="fcs")
            self.assertEqual(len(built), 1)
            self.assertEqual(built[0]["team"], "Howard")

    def test_rejects_wrong_subdivision_player_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player_path = root / "players.json"
            team_path = root / "teams.csv"
            player_path.write_text(json.dumps({
                "metadata": {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                             "classification": "fbs"},
                "season_stats": [], "usage": [], "rosters": [],
            }))
            team_path.write_text("team,games_sampled\n")
            with self.assertRaisesRegex(ValueError, "classification does not match"):
                build_player_inputs(player_path, team_path, root / "out.json",
                                    classification="fcs")

    def test_blocks_old_cache_when_latest_refresh_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player_path = root / "player_season_data.json"
            team_path = root / "teams.csv"
            player_path.write_text(json.dumps({
                "metadata": {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                             "classification": "fbs"},
                "season_stats": [], "usage": [], "rosters": [],
            }))
            (root / "player_data_status.json").write_text(json.dumps({
                "stats_available": False,
                "warnings": ["provider denied access"],
            }))
            team_path.write_text("team,games_sampled\n")
            with self.assertRaisesRegex(ValueError, "latest CFBD player stats refresh failed"):
                build_player_inputs(player_path, team_path, root / "out.json")

    def test_rejects_stale_player_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            player_path = root / "players.json"
            team_path = root / "teams.csv"
            player_path.write_text(json.dumps({
                "metadata": {"retrieved_at": "2020-01-01T00:00:00+00:00"},
                "season_stats": [], "usage": [],
            }))
            team_path.write_text("team,games_sampled\n")
            with self.assertRaisesRegex(ValueError, "days old"):
                build_player_inputs(player_path, team_path, root / "out.json")


if __name__ == "__main__":
    unittest.main()
