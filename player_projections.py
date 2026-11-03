"""Player projection engine for Doug's Elite Game Simulator.

Projections require a confirmed active starter. All numeric inputs must be
finite and physically plausible. These are conditional projections based on
supplied inputs, not independently verified live player data.
"""
import math

from player_availability import is_confirmed_starter


def _number(name, value, minimum=0.0, maximum=None):
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) or value < minimum
            or (maximum is not None and value > maximum)):
        raise ValueError(f"{name} must be a finite number in the valid range.")
    return value


def validate_projection_player(player):
    """Block projections for unconfirmed or inactive players."""
    if not is_confirmed_starter(player):
        raise ValueError(
            f"Projection blocked for {player['name']}: "
            "player is not a confirmed active starter."
        )


def project_quarterback(
    player, completions, opponent_yards_per_completion,
    passing_tds=0, interceptions=0
):
    validate_projection_player(player)
    _number("completions", completions, maximum=70)
    _number("opponent_yards_per_completion", opponent_yards_per_completion, maximum=40)
    _number("passing_tds", passing_tds, maximum=10)
    _number("interceptions", interceptions, maximum=10)
    return {
        "player": player["name"],
        "team": player["team"],
        "completions": completions,
        "passing_yards": round(completions * opponent_yards_per_completion, 2),
        "passing_tds": passing_tds,
        "interceptions": interceptions,
    }


def project_running_back(
    player, carries, yards_per_carry, receptions=0,
    receiving_yards=0, touchdowns=0
):
    validate_projection_player(player)
    _number("carries", carries, maximum=50)
    _number("yards_per_carry", yards_per_carry, maximum=25)
    _number("receptions", receptions, maximum=25)
    _number("receiving_yards", receiving_yards, maximum=400)
    _number("touchdowns", touchdowns, maximum=8)
    return {
        "player": player["name"],
        "team": player["team"],
        "carries": carries,
        "rushing_yards": round(carries * yards_per_carry, 2),
        "receptions": receptions,
        "receiving_yards": receiving_yards,
        "touchdowns": touchdowns,
    }


def project_receiver(
    player, targets, catch_rate, yards_per_reception, touchdowns=0
):
    validate_projection_player(player)
    _number("targets", targets, maximum=30)
    _number("catch_rate", catch_rate, maximum=1)
    _number("yards_per_reception", yards_per_reception, maximum=50)
    _number("touchdowns", touchdowns, maximum=8)
    receptions = targets * catch_rate
    return {
        "player": player["name"],
        "team": player["team"],
        "targets": targets,
        "receptions": round(receptions, 2),
        "receiving_yards": round(receptions * yards_per_reception, 2),
        "touchdowns": touchdowns,
    }


def project_player_workload(
    player, projected_snaps, projected_routes=0,
    projected_targets=0, projected_carries=0,
    red_zone_opportunities=0,
):
    """Project a confirmed active starter's workload."""
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
        _number(stat, value, maximum=limits[stat])
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


if __name__ == "__main__":
    print("DOUG'S ELITE GAME SIMULATOR")
    print("CONDITIONAL PLAYER PROJECTION ENGINE READY")
    print("Availability must be independently verified.")
