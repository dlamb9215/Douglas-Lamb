import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ncaa.data.refresh import build_dataset, build_team_aliases, extract_stats, parse_advanced, resolve_play_counts, write_outputs


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

    def test_resolve_play_counts_prefers_advanced_totals(self):
        raw = {"plays": 295, "plays_allowed": 310}
        offense = {"plays": 461}
        defense = {"plays": 478}
        offense_plays, defense_plays = resolve_play_counts(
            raw, offense, defense, 8, "Alabama"
        )
        self.assertEqual(offense_plays / 8, 57.625)
        self.assertEqual(defense_plays / 8, 59.75)

    def test_resolve_play_counts_rejects_bad_fallback(self):
        raw = {"plays": 295, "plays_allowed": 310}
        with self.assertRaisesRegex(RuntimeError, "invalid offense plays/game"):
            resolve_play_counts(raw, {}, {}, 8, "Alabama")

    def test_team_aliases_include_mascot_and_abbreviation(self):
        aliases = build_team_aliases([{
            "school": "Howard", "mascot": "Bison", "abbreviation": "HOW",
            "alternateNames": ["Howard University"],
        }])
        self.assertEqual(aliases["howard bison"], "Howard")
        self.assertEqual(aliases["how"], "Howard")
        self.assertEqual(aliases["howard university"], "Howard")

    def test_build_dataset_supports_fcs_without_mixing_fbs(self):
        fcs_teams = [{"school": f"FCS Team {i}", "classification": "fcs"} for i in range(60)]
        fcs_game = {
            "id": 1001, "homePoints": 21, "awayPoints": 14,
            "homeTeam": "FCS Team 0", "awayTeam": "FCS Team 1",
        }
        team_box = {"id": 1001, "teams": [
            {"team": "FCS Team 0", "points": 21, "stats": [
                {"category": "totalPlays", "stat": "60"},
                {"category": "totalYards", "stat": "330"},
                {"category": "passAttempts", "stat": "30"},
                {"category": "passCompletions", "stat": "20"},
                {"category": "netPassingYards", "stat": "220"},
                {"category": "rushAttempts", "stat": "30"},
                {"category": "rushingYards", "stat": "110"},
            ]},
            {"team": "FCS Team 1", "points": 14, "stats": [
                {"category": "totalPlays", "stat": "60"},
                {"category": "totalYards", "stat": "300"},
                {"category": "passAttempts", "stat": "30"},
                {"category": "passCompletions", "stat": "18"},
                {"category": "netPassingYards", "stat": "180"},
                {"category": "rushAttempts", "stat": "30"},
                {"category": "rushingYards", "stat": "120"},
            ]},
        ]}
        def fake_api(path, params, api_key):
            if path == "/teams":
                return fcs_teams + [{"school": "FBS Team", "classification": "fbs"}]
            if path == "/games":
                return [fcs_game]
            if path == "/games/teams":
                return [team_box] if params.get("week") == 1 else []
            if path in {"/stats/season/advanced", "/ratings/elo"}:
                return []
            raise AssertionError(f"Unexpected endpoint {path}")
        with patch("ncaa.data.refresh.api_get", side_effect=fake_api):
            profiles, rankings, metadata = build_dataset(2026, "regular", "key", "fcs")
        self.assertEqual(len(profiles), 2)
        self.assertEqual(metadata["classification"], "fcs")
        self.assertEqual({p["classification"] for p in profiles}, {"fcs"})
        self.assertIn("FCS Team 0", rankings)
        self.assertNotIn("FBS Team", rankings)

    def test_fcs_outputs_use_separate_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            profiles = [{"team": "Howard", "classification": "fcs"}]
            write_outputs(profiles, {"Howard": {"games": 4}},
                          {"year": 2026, "classification": "fcs"}, Path(tmp), "fcs")
            self.assertTrue((Path(tmp) / "team_profiles_fcs.csv").exists())
            self.assertTrue((Path(tmp) / "team_rankings_fcs.json").exists())
            self.assertFalse((Path(tmp) / "team_profiles.csv").exists())

    def test_outputs_write_csv_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            profiles = [{
                "team": "Example U", "points_for": 30, "points_against": 20,
                "yards_per_play": 6.0, "yards_per_play_allowed": 5.0,
                "plays_per_game": 70, "points_per_drive": "",
                "turnovers_per_game": 1.0, "takeaways_per_game": 1.5,
                "turnover_margin_per_game": 0.5,
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
