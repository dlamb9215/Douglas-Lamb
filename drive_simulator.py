
"""Drive-based scoring engine for Doug's Elite Game Simulator.

This is a first-stage possession model, not a full play-by-play simulator.
"""
import random


def _drive_probabilities(points_per_game, drives):
    ppp = max(0.05, min(4.5, points_per_game / drives))

    touchdown = min(0.34, max(0.08, ppp * 0.115))
    field_goal = max(
        0.0,
        min(0.45, (ppp - 7.0 * touchdown) / 3.0)
    )

    if touchdown * 7.0 + field_goal * 3.0 < ppp:
        touchdown = min(
            0.48,
            touchdown + (
                ppp - touchdown * 7.0 - field_goal * 3.0
            ) / 7.0
        )

    if touchdown + field_goal > 0.92:
        scale = 0.92 / (touchdown + field_goal)
        touchdown *= scale
        field_goal *= scale

    empty = max(0.0, 1.0 - touchdown - field_goal)
    return empty, field_goal, touchdown


def _score_team(rng, expected_points, drives):
    _, field_goal_probability, touchdown_probability = (
        _drive_probabilities(expected_points, drives)
    )

    score = 0

    for _ in range(drives):
        draw = rng.random()

        if draw < touchdown_probability:
            score += 7
        elif draw < touchdown_probability + field_goal_probability:
            score += 3

    return score


def simulate_drive_game(
    home_mean,
    away_mean,
    spread,
    total,
    trials=100000,
    seed=42
):
    """Simulate discrete scoring drives and calculate probabilities."""

    if trials < 1:
        raise ValueError("Trials must be greater than zero.")

    if home_mean < 0 or away_mean < 0:
        raise ValueError("Expected scores cannot be negative.")

    rng = random.Random(seed)

    keys = (
        "home_win", "away_win", "tie",
        "home_cover", "away_cover", "spread_push",
        "over", "under", "total_push"
    )

    counts = dict.fromkeys(keys, 0)
    home_points = 0
    away_points = 0

    for _ in range(trials):
        # Shared game pace connects both teams' drive volume.
        pace = max(8, min(14, round(rng.gauss(11.0, 1.15))))

        home_drives = max(
            7, min(15, pace + rng.choice((-1, 0, 0, 1)))
        )
        away_drives = max(
            7, min(15, pace + rng.choice((-1, 0, 0, 1)))
        )

        home = _score_team(rng, home_mean, home_drives)
        away = _score_team(rng, away_mean, away_drives)

        margin = home - away
        game_total = home + away

        home_points += home
        away_points += away

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

    results["home_avg"] = home_points / trials
    results["away_avg"] = away_points / trials

    return results
