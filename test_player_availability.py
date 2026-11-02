import unittest

from player_availability import (
    validate_player,
    validate_roster,
    get_active_players,
    get_confirmed_starters,
)


class TestPlayerAvailability(unittest.TestCase):

    def setUp(self):
        self.players = [
            {
                "name": "Player One",
                "team": "BUF",
                "position": "QB",
                "status": "active",
                "starter": True,
            },
            {
                "name": "Player Two",
                "team": "BUF",
                "position": "RB",
                "status": "questionable",
                "starter": False,
            },
            {
                "name": "Player Three",
                "team": "BUF",
                "position": "WR",
                "status": "out",
                "starter": False,
            },
        ]

    def test_valid_roster(self):
        self.assertTrue(validate_roster(self.players))

    def test_active_players(self):
        active = get_active_players(self.players, "BUF")
        self.assertEqual(len(active), 1)

    def test_confirmed_starters(self):
        starters = get_confirmed_starters(self.players, "BUF")
        self.assertEqual(len(starters), 1)
        self.assertEqual(starters[0]["position"], "QB")

    def test_questionable_player_excluded(self):
        active = get_active_players(self.players)
        names = [p["name"] for p in active]
        self.assertNotIn("Player Two", names)

    def test_out_player_excluded(self):
        active = get_active_players(self.players)
        names = [p["name"] for p in active]
        self.assertNotIn("Player Three", names)


if __name__ == "__main__":
    unittest.main()