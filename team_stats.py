
"""
DOUG'S ELITE GAME SIMULATOR
NFL TEAM STATISTICS AND MATCHUP ENGINE
"""

REQUIRED_CATEGORIES = {
    "offense": [
        "passing",
        "rushing",
        "total"
    ],
    "defense": [
        "passing",
        "rushing",
        "total"
    ]
}


def validate_team(team):
    """Check that required team data is supplied."""
    if not isinstance(team, dict):
        raise ValueError("Team data must be a dictionary.")

    if not team.get("name"):
        raise ValueError("Team name is required.")

    for section, categories in REQUIRED_CATEGORIES.items():
        if section not in team:
            raise ValueError(f"Missing section: {section}")

        for category in categories:
            if category not in team[section]:
                raise ValueError(
                    f"Missing {section}: {category}"
                )

    return True


def rank_advantage(offense_rank, defense_rank):
    """
    Lower NFL rank is better.
    Positive result favors the offense.
    """
    if offense_rank is None or defense_rank is None:
        return None

    return defense_rank - offense_rank


def compare_teams(team_a, team_b):
    """
    Compare both teams' offenses against
    the opposing team's defenses.
    """

    validate_team(team_a)
    validate_team(team_b)

    matchups = [
        ("Passing", "passing"),
        ("Rushing", "rushing"),
        ("Total offense", "total")
    ]

    results = []

    for label, category in matchups:

        a_offense = team_a["offense"][category]
        b_defense = team_b["defense"][category]

        b_offense = team_b["offense"][category]
        a_defense = team_a["defense"][category]

        a_edge = rank_advantage(
            a_offense.get("rank"),
            b_defense.get("rank")
        )

        b_edge = rank_advantage(
            b_offense.get("rank"),
            a_defense.get("rank")
        )

        results.append({
            "category": label,
            "team_a_offense": a_offense,
            "team_b_defense": b_defense,
            "team_b_offense": b_offense,
            "team_a_defense": a_defense,
            "team_a_advantage": a_edge,
            "team_b_advantage": b_edge
        })

    return {
        "team_a": team_a["name"],
        "team_b": team_b["name"],
        "matchups": results
    }


def print_matchup_report(report):

    print("\nDOUG'S ELITE GAME SIMULATOR")
    print("NFL TEAM VS TEAM BREAKDOWN")
    print("=" * 45)

    print(
        f"\n{report['team_a']} VS "
        f"{report['team_b']}"
    )

    for matchup in report["matchups"]:

        print("\n" + matchup["category"].upper())

        print(
            f"{report['team_a']} offense rank: "
            f"{matchup['team_a_offense'].get('rank', 'N/A')}"
        )

        print(
            f"{report['team_b']} defense rank: "
            f"{matchup['team_b_defense'].get('rank', 'N/A')}"
        )

        print(
            f"{report['team_b']} offense rank: "
            f"{matchup['team_b_offense'].get('rank', 'N/A')}"
        )

        print(
            f"{report['team_a']} defense rank: "
            f"{matchup['team_a_defense'].get('rank', 'N/A')}"
        )

        print(
            f"{report['team_a']} matchup edge: "
            f"{matchup['team_a_advantage']}"
        )

        print(
            f"{report['team_b']} matchup edge: "
            f"{matchup['team_b_advantage']}"
        )

    print("\nMATCHUP COMPARISON COMPLETE")


def compare_turnovers(team_a, team_b):

    for team in [team_a, team_b]:

        if "turnovers" not in team:
            raise ValueError(
                "Turnover statistics are required."
            )

        print("\n", team["name"], "TURNOVERS")

        for key, value in team["turnovers"].items():
            print(f"{key}: {value}")

def compare_stat_advantage(team_a, team_b):
    """Compare actual offensive production against opposing defense."""

    results = {}

    for category in ("passing", "rushing", "total"):
        offense = team_a["offense"][category]
        defense = team_b["defense"][category]

        offense_yards = offense.get("yards_per_game")
        defense_allowed = defense.get("yards_allowed_per_game")

        if offense_yards is None or defense_allowed is None:
            results[category] = None
        else:
            results[category] = round(
                offense_yards - defense_allowed, 2
            )

    return results
if __name__ == "__main__":

    print("Doug's Elite Game Simulator")
    print("NFL Team Statistics Engine Ready")
    print("Waiting for verified team statistics.")
