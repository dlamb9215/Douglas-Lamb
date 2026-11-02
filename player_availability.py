
"""
DOUG'S ELITE GAME SIMULATOR
PLAYER AVAILABILITY AND STARTER VALIDATION

Only confirmed active players and confirmed starters
are eligible for final player projections.
"""

VALID_STATUSES = {
    "active",
    "inactive",
    "questionable",
    "doubtful",
    "out",
    "unknown",
}

VALID_POSITIONS = {
    "QB", "RB", "WR", "TE", "K", "DEF"
}


def validate_player(player):
    """Validate one player record."""

    required = ("name", "team", "position", "status", "starter")

    for field in required:
        if field not in player:
            raise ValueError(f"Player missing required field: {field}")

    if not player["name"].strip():
        raise ValueError("Player name cannot be empty.")

    if player["status"] not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status for {player['name']}: "
            f"{player['status']}"
        )

    if player["position"] not in VALID_POSITIONS:
        raise ValueError(
            f"Invalid position for {player['name']}: "
            f"{player['position']}"
        )

    if not isinstance(player["starter"], bool):
        raise ValueError(
            f"Starter status must be true or false for "
            f"{player['name']}."
        )

    return True


def validate_roster(players):
    """Validate all player records."""

    if not isinstance(players, list):
        raise ValueError("Player roster must be a list.")

    seen = set()

    for player in players:
        if not isinstance(player, dict):
            raise ValueError("Every player must be a dictionary.")

        validate_player(player)

        key = (
            player["team"],
            player["name"].strip().lower()
        )

        if key in seen:
            raise ValueError(
                f"Duplicate player: {player['name']}"
            )

        seen.add(key)

    return True


def is_active(player):
    """Return true only for officially active players."""

    validate_player(player)
    return player["status"] == "active"


def is_confirmed_starter(player):
    """Return true only for active confirmed starters."""

    validate_player(player)

    return (
        player["status"] == "active"
        and player["starter"] is True
    )


def get_active_players(players, team=None):
    """Return active players, optionally filtered by team."""

    validate_roster(players)

    return [
        player for player in players
        if is_active(player)
        and (team is None or player["team"] == team)
    ]


def get_confirmed_starters(players, team=None):
    """Return confirmed active starters."""

    validate_roster(players)

    return [
        player for player in players
        if is_confirmed_starter(player)
        and (team is None or player["team"] == team)
    ]


def get_player_status_report(players, team):
    """Summarize availability for one team."""

    validate_roster(players)

    team_players = [
        player for player in players
        if player["team"] == team
    ]

    return {
        "team": team,
        "total_players": len(team_players),
        "active": sum(
            p["status"] == "active" for p in team_players
        ),
        "inactive": sum(
            p["status"] == "inactive" for p in team_players
        ),
        "out": sum(
            p["status"] == "out" for p in team_players
        ),
        "questionable": sum(
            p["status"] == "questionable" for p in team_players
        ),
        "doubtful": sum(
            p["status"] == "doubtful" for p in team_players
        ),
        "unknown": sum(
            p["status"] == "unknown" for p in team_players
        ),
        "confirmed_starters": len(
            get_confirmed_starters(team_players)
        ),
    }


if __name__ == "__main__":
    print("DOUG'S ELITE GAME SIMULATOR")
    print("PLAYER AVAILABILITY ENGINE READY")
    print("Unverified players are never assumed active.")
