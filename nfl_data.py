
"""
DOUG'S ELITE GAME SIMULATOR
NFL TEAM STATISTICS DATA ENGINE

Loads verified NFL statistics, validates team data,
and calculates offensive and defensive rankings.
"""

import json
from pathlib import Path

from nfl_teams import NFL_TEAMS


CATEGORIES = ("passing", "rushing", "total")

REQUIRED_STATS = {
    "passing": [
        "yards_per_game",
        "attempts_per_game",
        "completions_per_game",
        "completion_pct",
        "yards_per_attempt",
        "touchdowns",
        "interceptions",
        "first_downs_per_game",
    ],
    "rushing": [
        "yards_per_game",
        "attempts_per_game",
        "yards_per_carry",
        "touchdowns",
        "first_downs_per_game",
    ],
    "total": [
        "yards_per_game",
        "plays_per_game",
        "yards_per_play",
    ],
}


def validate_source_data(records):
    """Validate incoming statistics."""

    if not isinstance(records, list):
        raise ValueError("Statistics must be a list.")

    seen = set()

    for record in records:
        team = record.get("team")

        if team not in NFL_TEAMS:
            raise ValueError(f"Invalid NFL team: {team}")

        if team in seen:
            raise ValueError(f"Duplicate team: {team}")

        seen.add(team)

        for section in ("offense", "defense"):
            if section not in record:
                raise ValueError(
                    f"{team} missing {section}"
                )

            for category in CATEGORIES:
                if category not in record[section]:
                    raise ValueError(
                        f"{team} missing {section} {category}"
                    )

    return True


def calculate_rankings(database):
    """Rank all teams in each statistical category."""

    for section in ("offense", "defense"):

        for category in CATEGORIES:

            field = "yards_per_game"

            ranked = []

            for abbreviation, team in database.items():

                stats = team[section][category]

                value = stats.get(field)

                if value is not None:
                    ranked.append((abbreviation, value))

            # Offense: higher yards rank better.
            # Defense: lower yards allowed rank better.
            ranked.sort(
                key=lambda item: item[1],
                reverse=(section == "offense")
            )

            for rank, (abbreviation, value) in enumerate(
                ranked, start=1
            ):
                database[abbreviation][section][category][
                    "rank"
                ] = rank

    return database


def build_team_database(records):
    """Build the simulator's NFL database."""

    validate_source_data(records)

    database = {}

    for record in records:

        abbreviation = record["team"]

        database[abbreviation] = {
            "name": NFL_TEAMS[abbreviation],

            "offense": record["offense"],

            "defense": record["defense"],

            "turnovers": record.get(
                "turnovers",
                {
                    "takeaways": None,
                    "giveaways": None,
                    "differential": None
                }
            )
        }

    return calculate_rankings(database)


def load_team_stats(filename="nfl_team_stats.json"):
    """Load verified statistics from a JSON file."""

    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"{filename} not found. "
            "Add verified NFL statistics first."
        )

    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    return build_team_database(records)


def get_team_stats(database, abbreviation):
    """Retrieve one team's statistics."""

    if abbreviation not in database:
        raise ValueError(
            f"Unknown NFL team: {abbreviation}"
        )

    return database[abbreviation]


def compare_team_stats(database, team_a, team_b):
    """Compare both teams' offensive and defensive rankings."""

    first = get_team_stats(database, team_a)
    second = get_team_stats(database, team_b)

    report = {}

    for category in CATEGORIES:

        report[category] = {
            "team_a_offense": first["offense"][category],
            "team_b_defense": second["defense"][category],

            "team_b_offense": second["offense"][category],
            "team_a_defense": first["defense"][category],
        }

    return report


if __name__ == "__main__":

    print("DOUG'S ELITE GAME SIMULATOR")
    print("NFL STATISTICS ENGINE")
    print("=========================")
    print("32 NFL teams recognized.")
    print("Statistics loader ready.")
    print("Waiting for verified NFL data.")
