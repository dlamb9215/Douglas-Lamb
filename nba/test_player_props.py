import unittest
from datetime import date, datetime, timezone, timedelta
from nba.player_props import parse_gamelog, project_player, _walk_players, confirmed_minutes, build_matchup_player_projections, validate_lineup_context

class TestNBAPlayerProps(unittest.TestCase):
    def test_roster_walker_ignores_team_objects(self):
        payload = {
            "team": {"id": "2", "displayName": "Boston Celtics"},
            "athletes": [
                {"id": "10", "fullName": "Player One", "displayName": "Player One", "position": {"abbreviation": "G"}},
                {"id": "11", "displayName": "Player Two", "jersey": "4", "position": {"abbreviation": "F"}},
            ],
        }
        found = list(_walk_players(payload))
        self.assertEqual({str(player["id"]) for player in found}, {"10", "11"})

    def test_parse_gamelog_from_espn_v3_shape(self):
        payload = {
            "labels": ["MIN", "FG", "3PT", "FT", "REB", "AST", "STL", "BLK", "PTS"],
            "events": {
                "1": {"gameDate": "2026-11-01T00:00Z", "opponent": {"abbreviation": "NYK"}},
                "2": {"gameDate": "2026-11-03T00:00Z", "opponent": {"abbreviation": "MIA"}},
            },
            "seasonTypes": [{
                "displayName": "2026-27 Regular Season",
                "categories": [{"events": [
                    {"eventId": "1", "stats": ["34", "10-20", "2-5", "4-4", "8", "6", "1", "0", "26"]},
                    {"eventId": "2", "stats": ["DNP", "--", "--", "--", "--", "--", "--", "--", "--"]},
                ]}],
            }],
        }
        rows = parse_gamelog(payload, {"id": "p"}, None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["minutes"], 34)
        self.assertEqual(rows[0]["points"], 26)
        self.assertEqual(rows[0]["rebounds"], 8)
        self.assertEqual(rows[0]["assists"], 6)

    def test_projector_excludes_questionable_and_out_players(self):
        player = {"id": "1", "name": "Test Player", "position": "G"}
        games = [{"minutes": 30, "points": 20, "rebounds": 5, "assists": 6} for _ in range(8)]
        self.assertIsNone(project_player(player, games, "Questionable"))
        self.assertIsNone(project_player(player, games, "Out"))

    def test_projector_generates_points_rebounds_assists_and_pra(self):
        player = {"id": "1", "name": "Test Player", "position": "G"}
        games = [
            {"minutes": 30 + (i % 3), "points": 18 + i, "rebounds": 4 + (i % 2), "assists": 5 + (i % 3)}
            for i in range(10)
        ]
        result = project_player(player, games, "Available", trials=5000, seed=10, lines={"points": 22.5, "rebounds": 5.5})
        self.assertIn("points", result["projections"])
        self.assertIn("rebounds", result["projections"])
        self.assertIn("assists", result["projections"])
        self.assertIn("pra", result["projections"])
        self.assertIsNotNone(result["projections"]["points"]["over_probability"])
        self.assertGreater(result["projected_minutes"], 0)

    def test_confirmed_lineup_gate(self):
        self.assertEqual(confirmed_minutes({"confirmed": True, "status": "available", "minutes": 34, "minutes_sd": 2}),
                         (34.0, 2.0, None))
        self.assertIsNotNone(confirmed_minutes({"confirmed": False, "status": "available", "minutes": 34, "minutes_sd": 2})[2])
        self.assertIsNotNone(confirmed_minutes({"confirmed": True, "status": "questionable", "minutes": 34, "minutes_sd": 2})[2])
        self.assertIsNotNone(confirmed_minutes({"confirmed": True, "status": "available", "minutes": 34, "minutes_sd": 9})[2])

    def test_confirmed_lineup_source_and_freshness_gate(self):
        now = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
        valid = {"source": "official team lineup", "confirmed_at": "2026-11-09T17:30:00+00:00",
                 "teams": {"BOS": {}, "NYK": {}}}
        self.assertTrue(validate_lineup_context(valid, ["BOS", "NYK"], now)[0])
        stale = dict(valid, confirmed_at="2026-11-08T00:00:00+00:00")
        self.assertFalse(validate_lineup_context(stale, ["BOS", "NYK"], now)[0])
        missing_source = dict(valid, source="")
        self.assertFalse(validate_lineup_context(missing_source, ["BOS", "NYK"], now)[0])
        missing_team = dict(valid, teams={"BOS": {}})
        self.assertFalse(validate_lineup_context(missing_team, ["BOS", "NYK"], now)[0])

    def test_player_props_withheld_without_confirmed_lineups(self):
        result = build_matchup_player_projections("BOS", "NYK", date(2026, 11, 9))
        self.assertEqual(result["teams"], {"BOS": [], "NYK": []})
        self.assertIn("withheld", result["warnings"][0].lower())

    def test_confirmed_minutes_override_historical_minutes(self):
        player = {"id": "1", "name": "Test Player", "position": "G"}
        games = [{"minutes": 20, "points": 12, "rebounds": 3, "assists": 4} for _ in range(8)]
        result = project_player(player, games, "Available", trials=5000, seed=4,
                                confirmed_minutes=35, confirmed_minutes_sd=1.5)
        self.assertEqual(result["projected_minutes"], 35)
        self.assertEqual(result["minutes_source"], "confirmed game-specific input")

    def test_projector_rejects_small_samples_and_low_minutes(self):
        player = {"id": "1", "name": "Test Player", "position": "G"}
        games = [{"minutes": 5, "points": 3, "rebounds": 1, "assists": 1} for _ in range(10)]
        self.assertIsNone(project_player(player, games))
        self.assertIsNone(project_player(player, games[:4]))

if __name__ == "__main__":
    unittest.main()
