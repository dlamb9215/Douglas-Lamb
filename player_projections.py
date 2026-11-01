"""
DOUG'S ELITE GAME SIMULATOR
PLAYER PROJECTION ENGINE
"""


def project_quarterback(
    completions,
    opponent_yards_per_completion,
    passing_tds=0,
    interceptions=0
):
    return {
        "completions": completions,
        "passing_yards": round(
            completions * opponent_yards_per_completion, 2
        ),
        "passing_tds": passing_tds,
        "interceptions": interceptions
    }


def project_running_back(
    carries,
    yards_per_carry,
    receptions=0,
    receiving_yards=0,
    touchdowns=0
):
    return {
        "carries": carries,
        "rushing_yards": round(
            carries * yards_per_carry, 2
        ),
        "receptions": receptions,
        "receiving_yards": receiving_yards,
        "touchdowns": touchdowns
    }


def project_receiver(
    targets,
    catch_rate,
    yards_per_reception,
    touchdowns=0
):
    receptions = targets * catch_rate

    return {
        "targets": targets,
        "receptions": round(receptions, 2),
        "receiving_yards": round(
            receptions * yards_per_reception, 2
        ),
        "touchdowns": touchdowns
    }


if __name__ == "__main__":
    print("DOUG'S ELITE GAME SIMULATOR")
    print("PLAYER PROJECTION ENGINE READY")