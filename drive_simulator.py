
"""Drive-based NFL scoring simulation for Doug's Elite Game Simulator.

A simplified possession model, not a play-by-play engine.
The spread argument is the home team's handicap.
"""
import random


def _clip(value, low, high):
    return max(low, min(high, value))


def _drive_outcomes(points_per_game, drives, efficiency=1.0):
    points_per_drive = max(
        0.0, points_per_game * efficiency / max(1, drives)
    )

    # Allocate expected scoring between touchdowns and field goals.
    td_probability = points_per_drive * 0.62 / 7.0
    fg_probability = points_per_drive * 0.38 / 3.0

    td_probability = _clip(td_probability, 0.0, 0.65)
    fg_probability = _clip(fg_probability, 0.0, 0.65)

    if td_probability + fg_probability > 0.90:
        scale = 0.90 / (td_probability + fg_probability)
        td_probability *= scale
        fg_probability *= scale

    return td_probability, fg_probability


def _score_team(rng, expected_points, drives, efficiency):
    td_probability, fg_probability = _drive_outcomes(
        expected_points, drives, efficiency
    )

    score = 0

    for _ in range(drives):
        draw = rng.random()

        if draw < td_probability:
            score += 7
        elif draw < td_probability + fg_probability:
            score += 3

    return score


def _game_script_multiplier(score_margin):
    """Adjust scoring efficiency based on the current score."""

    if score_margin >= 14:
        return 0.88
    elif score_margin >= 7:
        return 0.94
    elif score_margin <= -14:
        return 1.10
    elif score_margin <= -7:
        return 1.05

    return 1.00


def _score_one_drive(
    rng,
    expected_points,
    drives,
    efficiency,
    script_multiplier,
):
    """Simulate one scoring drive with a game-script adjustment."""

    adjusted_points = expected_points * script_multiplier

    td_probability, fg_probability = _drive_outcomes(
        adjusted_points,
        drives,
        efficiency,
    )

    draw = rng.random()

    if draw < td_probability:
        return 7
    elif draw < td_probability + fg_probability:
        return 3

    return 0

def simulate_drive_game(
    home_mean,
    away_mean,
    spread,
    total,
    trials=100000,
    seed=42,
    first_half=False,
):
    """Return simulated win, spread, total and score probabilities."""

    if trials < 1:
        raise ValueError("Trials must be greater than zero.")

 
    home_score_sum = 0
    away_score_sum = 0

    for _ in range(trials):
        if first_half:
            pace = _clip(round(rng.gauss(5.3, 0.8)), 3, 8)
            min_drives, max_drives = 3, 8
            home_target = home_mean / 2
            away_target = away_mean / 2
        else:
            pace = _clip(round(rng.gauss(10.6, 1.2)), 7, 15)
            min_drives, max_drives = 7, 15
            home_target = home_mean
            away_target = away_mean

        home_drives = int(_clip(
            pace + rng.choice((-1, 0, 0, 1)),
            min_drives, max_drives
        ))
        away_drives = int(_clip(
            pace + rng.choice((-1, 0, 0, 1)),
            min_drives, max_drives
        ))

        # Small game-level efficiency variation.
        home_efficiency = _clip(rng.gauss(1.0, 0.10), 0.70, 1.30)
        away_efficiency = _clip(rng.gauss(1.0, 0.10), 0.70, 1.30)

        home = _score_team(
            rng, home_target, home_drives, home_efficiency
        )
        away = _score_team(
            rng, away_target, away_drives, away_efficiency
        )

        margin = home - away
        game_total = home + away

        home_score_sum += home
        away_score_sum += away

        if margin > 0:
            counts["home_win"] += 1
        elif margin < 0:
            counts["away_win"] += 1
        else:
            counts["tie"] += 1

        cover_margin = margin + spread

        if cover_margin > 0:
            counts["home_cover"] += 1
        elif cover_margin < 0:
            counts["away_cover"] += 1
        else:
            counts["spread_push"] += 1

        if game_total > total:
            counts["over"] += 1
        elif game_total < total:
            counts["under"] += 1
        else:
            counts["total_push"] += 1

    results = {
        key: value * 100.0 / trials
        for key, value in counts.items()
    }

    results["home_avg"] = home_score_sum / trials
    results["away_avg"] = away_score_sum / trials

            return results
