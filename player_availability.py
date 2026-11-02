
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


def adjust_injury_workload(
    player,
    projected_snaps,
    practice_status="full",
    snap_limit=None,
    backup_snap_bonus=0,
):
    """
    Adjust projected workload for injury-related limitations.
    Only confirmed active starters receive projections.
    """

    validate_player(player)

    if player["status"] != "active" or player.get("starter") is not True:
        raise ValueError(
            "Injury workload adjustment requires an active starter."
        )

    if practice_status not in {"full", "limited", "dnp"}:
        raise ValueError("Invalid practice status.")

    values = {
        "projected_snaps": projected_snaps,
        "backup_snap_bonus": backup_snap_bonus,
    }

    for field, value in values.items():
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            raise ValueError(f"Invalid value for {field}.")

    if projected_snaps > 100 or backup_snap_bonus > 100:
        raise ValueError("Snap projections cannot exceed 100.")

    if snap_limit is not None:
        if (
            not isinstance(snap_limit, (int, float))
            or isinstance(snap_limit, bool)
            or not 0 <= snap_limit <= 100
        ):
            raise ValueError("Snap limit must be between 0 and 100.")

    practice_multipliers = {
        "full": 1.00,
        "limited": 0.85,
        "dnp": 0.70,
    }

    adjusted_snaps = (
        projected_snaps * practice_multipliers[practice_status]
    )

    if snap_limit is not None:
        adjusted_snaps = min(adjusted_snaps, snap_limit)

    adjusted_snaps = min(
        100,
        adjusted_snaps + backup_snap_bonus
    )

    return {
        "player": player["name"],
        "team": player["team"],
        "practice_status": practice_status,
        "original_snaps": projected_snaps,
        "adjusted_snaps": round(adjusted_snaps, 2),
        "snap_limit": snap_limit,
        "backup_snap_bonus": backup_snap_bonus,
    }

if __name__ == "__main__":
    print("DOUG'S ELITE GAME SIMULATOR")
    print("PLAYER AVAILABILITY ENGINE READY")
    print("Unverified players are never assumed active.")
