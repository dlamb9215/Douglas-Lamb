
"""
DOUG'S ELITE GAME SIMULATOR
NFL MATCHUP ENGINE
"""

from nfl_teams import create_team_database
from team_stats import compare_teams, print_matchup_report

DATABASE = create_team_database()


def update_team_stats(
    abbreviation,
    offense,
    defense,
    takeaways,
    giveaways
):
    if abbreviation not in DATABASE:
        raise ValueError("Unknown NFL team")

    team = DATABASE[abbreviation]

    team["offense"] = offense
    team["defense"] = defense

    team["turnovers"] = {
        "takeaways": takeaways,
        "giveaways": giveaways,
        "differential": takeaways - giveaways
    }

    return team


def analyze_matchup(team_a, team_b):
    if team_a not in DATABASE or team_b not in DATABASE:
        raise ValueError("Invalid team abbreviation")

    first = DATABASE[team_a]
    second = DATABASE[team_b]

    report = compare_teams(first, second)

    print_matchup_report(report)

    print("\nTURNOVER COMPARISON")

    for team in [first, second]:
        turnovers = team["turnovers"]

        print("\n" + team["name"])
        print("Takeaways:", turnovers["takeaways"])
        print("Giveaways:", turnovers["giveaways"])
        print("Differential:", turnovers["differential"])

    return report


if __name__ == "__main__":
    print("DOUG'S ELITE GAME SIMULATOR")
    print("MATCHUP ENGINE READY")
    print("32 NFL teams loaded")
