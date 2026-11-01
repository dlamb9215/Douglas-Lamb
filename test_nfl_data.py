import unittest

from nfl_data import (
    load_team_stats,
    get_team_stats,
    compare_team_stats
)


class TestNFLData(unittest.TestCase):

    def setUp(self):
        self.database = load_team_stats()

    def test_all_32_teams_loaded(self):
        self.assertEqual(len(self.database), 32)

    def test_all_teams_have_names(self):
        for team in self.database.values():
            self.assertTrue(team["name"])

    def test_team_lookup(self):
        team = get_team_stats(self.database, "BUF")
        self.assertEqual(team["name"], "Buffalo Bills")

    def test_matchup_comparison(self):
        result = compare_team_stats(
            self.database, "BUF", "KC"
        )
        self.assertIn("passing", result)
        self.assertIn("rushing", result)
        self.assertIn("total", result)


if __name__ == "__main__":
    unittest.main()