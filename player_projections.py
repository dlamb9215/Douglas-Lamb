
"""
DOUG'S ELITE GAME SIMULATOR
PLAYER PROJECTION ENGINE

Only confirmed active starters may receive projections.
"""

from player_availability import is_confirmed_starter


def validate_projection_player(player):
    """Block projections for unconfirmed or inactive players."""

    if not is_confirmed_starter(player):
        raise ValueError(
            f"Projection blocked for {player['name']}: "
            "player is not a confirmed active starter."
        )


def project_quarterback(
    player,
    completions,
    opponent_yards_per_completion,
    passing_tds=0,
    interceptions=0
):
    validate_projection_player(player)

    return {
        "player": player["name"],
        "team": player["team"],
        "completions": completions,
        "passing_yards": round(
            completions * opponent_yards_per_completion, 2
        ),
        "passing_tds": passing_tds,
        "interceptions": interceptions
    }


def project_running_back(
    player,
    carries,
    yards_per_carry,
    receptions=0,
    receiving_yards=0,
    touchdowns=0
):
    validate_projection_player(player)

    return {
        "player": player["name"],
        "team": player["team"],
        "carries": carries,
        "rushing_yards": round(
            carries * yards_per_carry, 2
        ),
        "receptions": receptions,
        "receiving_yards": receiving_yards,
        "touchdowns": touchdowns
    }


def project_receiver(
    player,
    targets,
    catch_rate,
    yards_per_reception,
    touchdowns=0
):
    validate_projection_player(player)

    receptions = targets * catch_rate

    return {
        "player": player["name"],
        "team": player["team"],
        "targets": targets,
        "receptions": round(receptions, 2),
        "receiving_yards": round(
            receptions * yards_per_reception, 2
        ),
        "touchdowns": touchdowns
    }


if __name__ == "__main__":
    print("DOUG'S ELITE GAME SIMULATOR")
    print("AVAILABILITY-VERIFIED PROJECTIONS READY")



def project_player_workload(
    player,
    projected_snaps,
    projected_routes=0,
    projected_targets=0,
    projected_carries=0,
    red_zone_opportunities=0,
):
    """Project player workload for Doug's Elite Game Simulator."""

    validate_projection_player(player)

    workload = {
        "projected_snaps": projected_snaps,
        "projected_routes": projected_routes,
        "projected_targets": projected_targets,
        "projected_carries": projected_carries,
        "red_zone_opportunities": red_zone_opportunities,
    }

    limits = {
        "projected_snaps": 100,
        "projected_routes": 100,
        "projected_targets": 30,
        "projected_carries": 40,
        "red_zone_opportunities": 20,
    }

    for stat, value in workload.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{stat} must be numeric")

        if value < 0 or value > limits[stat]:
            raise ValueError(f"Invalid workload value: {stat}")

    if projected_routes > projected_snaps:
        raise ValueError("Routes cannot exceed projected snaps")

    if projected_targets > projected_routes:
        raise ValueError("Targets cannot exceed projected routes")

    return {
        "player": player["name"],
        "team": player["team"],
        "position": player["position"],
        **workload,
    }
