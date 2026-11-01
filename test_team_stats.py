
import unittest

from team_stats import (
    validate_team,
    compare_teams,
    rank_advantage,
    compare_stat_advantage
)


def make_team(name, offense_rank, defense_rank):
    return {
        "name": name,
        "offense": {
            "passing": {"rank": offense_rank},
            "rushing": {"rank": offense_rank},
            "total": {"rank": offense_rank}
        },
        "defense": {
            "passing": {"rank": defense_rank},
            "rushing": {"rank": defense_rank},
            "total": {"rank": defense_rank}
        },
        "turnovers": {
            "takeaways": 10,
            "giveaways": 8
        }
    }


class TestTeamStats(unittest.TestCase):

    def setUp(self):
        self.team_a = make_team("Team A", 5, 20)
        self.team_b = make_team("Team B", 15, 10)

    def test_valid_team(self):
        self.assertTrue(validate_team(self.team_a))

    def test_invalid_team(self):
        with self.assertRaises(ValueError):
            validate_team({"name": "Incomplete"})

    def test_rank_advantage(self):
        self.assertEqual(rank_advantage(5, 20), 15)

    def test_compare_teams(self):
        result = compare_teams(
            self.team_a,
            self.team_b
        )

        self.assertEqual(result["team_a"], "Team A")
        self.assertEqual(result["team_b"], "Team B")
        self.assertEqual(len(result["matchups"]), 3)

    def test_passing_advantage(self):
        result = compare_teams(
            self.team_a,
            self.team_b
        )

        passing = result["matchups"][0]

        self.assertEqual(
            passing["team_a_advantage"], 5
        )

    def test_rushing_advantage(self):
        result = compare_teams(
            self.team_a,
            self.team_b
        )

        rushing = result["matchups"][1]

        self.assertEqual(
            rushing["team_b_advantage"], 5
        )


if __name__ == "__main__":
    unittest.main()
