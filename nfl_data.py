"""
DOUG'S ELITE GAME SIMULATOR
NFL TEAM STATISTICS DATA ENGINE

Validates NFL data, calculates rankings,
and checks whether matchup projections are safe.
"""

import json
import math
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


def is_valid_number(value):
    """Accept real finite numbers, but reject booleans."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_source_data(records):
    """Check team coverage and the structure of incoming data."""

    if not isinstance(records, list):
        raise ValueError("Statistics must be a list.")

    seen = set()

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Every team record must be an object.")

        team = record.get("team")

        if team not in NFL_TEAMS:
            raise ValueError(f"Invalid NFL team: {team}")

        if team in seen:
            raise ValueError(f"Duplicate team: {team}")

        seen.add(team)

        for section in ("offense", "defense"):
            section_data = record.get(section)

            if not isinstance(section_data, dict):
                raise ValueError(f"{team} missing {section} data.")

            for category in CATEGORIES:
                category_data = section_data.get(category)

                if not isinstance(category_data, dict):
                    raise ValueError(
                        f"{team} missing {section} {category} data."
                    )

                for field, value in category_data.items():
                    if value is not None and not is_valid_number(value):
                        raise ValueError(
                            f"{team} has invalid {section} "
                            f"{category} value for {field}."
                        )

        turnovers = record.get("turnovers", {})

        if not isinstance(turnovers, dict):
            raise ValueError(f"{team} has invalid turnover data.")

        for field in ("takeaways", "giveaways", "differential"):
            value = turnovers.get(field)

            if value is not None and not is_valid_number(value):
                raise ValueError(
                    f"{team} has invalid turnover value for {field}."
                )

    missing = set(NFL_TEAMS) - seen

    if missing:
        raise ValueError(
            "Missing NFL teams: " + ", ".join(sorted(missing))
        )

    return True


def calculate_rankings(database):
    """Rank teams using only available statistics."""

    for section in ("offense", "defense"):
        for category in CATEGORIES:
            ranked = []

            for abbreviation, team in database.items():
                stats = team[section][category]
                value = stats.get("yards_per_game")

                if is_valid_number(value):
                    ranked.append((abbreviation, value))

                stats.pop("rank", None)

            ranked.sort(
                key=lambda item: item[1],
                reverse=(section == "offense")
            )

            for rank, (abbreviation, _) in enumerate(
                ranked, start=1
            ):
                database[abbreviation][section][category]["rank"] = rank

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
                    "differential": None,
                }
            ),
        }

    return calculate_rankings(database)


def load_team_stats(filename="nfl_team_stats.json"):
    """Load and validate the NFL statistics file."""

    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"{filename} not found.")

    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    return build_team_database(records)


def get_team_stats(database, abbreviation):
    """Retrieve one team's statistics."""

    if abbreviation not in database:
        raise ValueError(f"Unknown NFL team: {abbreviation}")

    return database[abbreviation]


def get_missing_stats(team, section):
    """List required statistics that are not yet available."""

    missing = []

    for category, fields in REQUIRED_STATS.items():
        stats = team[section][category]

        for field in fields:
            if not is_valid_number(stats.get(field)):
                missing.append(f"{category}.{field}")

    return missing


def check_matchup_data(database, team_a, team_b):
    """Check whether both teams have complete required data."""

    first = get_team_stats(database, team_a)
    second = get_team_stats(database, team_b)

    missing = {}

    for abbreviation, team in (
        (team_a, first),
        (team_b, second),
    ):
        team_missing = []

        for section in ("offense", "defense"):
            for field in get_missing_stats(team, section):
                team_missing.append(f"{section}.{field}")

        turnovers = team["turnovers"]

        for field in ("takeaways", "giveaways", "differential"):
            if not is_valid_number(turnovers.get(field)):
                team_missing.append(f"turnovers.{field}")

        if team_missing:
            missing[abbreviation] = team_missing

    return {
        "ready": not missing,
        "missing": missing,
    }


def compare_team_stats(database, team_a, team_b):
    """Compare both teams' offense against the opponent's defense."""

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

    report["data_check"] = check_matchup_data(
        database, team_a, team_b
    )

    return report

def project_team_yardage(database, offense_team, defense_team):
    """Project a team's passing, rushing, and total yards."""

    offense = get_team_stats(database, offense_team)["offense"]
    defense = get_team_stats(database, defense_team)["defense"]

    passing = (
        offense["passing"]["yards_per_game"]
        + defense["passing"]["yards_per_game"]
    ) / 2

    rushing = (
        offense["rushing"]["yards_per_game"]
        + defense["rushing"]["yards_per_game"]
    ) / 2

    return {
        "passing_yards": round(passing, 1),
        "rushing_yards": round(rushing, 1),
        "total_yards": round(passing + rushing, 1),
    }


def project_matchup_yardage(database, home_team, away_team):
    """Project yardage for both teams in a matchup."""

    return {
        home_team: project_team_yardage(
            database, home_team, away_team
        ),
        away_team: project_team_yardage(
            database, away_team, home_team
        ),
    }
if __name__ == "__main__":
    database = load_team_stats()

    print("DOUG'S ELITE GAME SIMULATOR")
    print("NFL STATISTICS ENGINE")
    print("=========================")
    print(f"Teams loaded: {len(database)}")
    print("Statistics structure validated.")

    ready_teams = sum(
        1 for team in database.values()
        if not get_missing_stats(team, "offense")
        and not get_missing_stats(team, "defense")
    )

    print(f"Teams with complete offense and defense: {ready_teams}/32")
    print("Missing statistics remain unavailable, not zero.")