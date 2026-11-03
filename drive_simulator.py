"""Drive-based NFL scoring simulation for Doug's Elite Game Simulator.

This is a possession-level approximation, not a play-by-play engine.
The spread argument is the home team's handicap (e.g. -3.5 means
the home team must win by more than 3.5 to cover).
"""
import math
import random


def _clip(value, low, high):
    return max(low, min(high, value))


def _drive_outcomes(points_per_game, drives, efficiency=1.0):
    """Convert expected team points into per-drive TD/FG probabilities."""
    if drives < 1:
        raise ValueError("Each team must have at least one drive.")

    points_per_drive = max(
        0.0, points_per_game * efficiency / drives
    )

    # Allocate expected scoring between touchdowns and field goals.
    td_probability = _clip(points_per_drive * 0.62 / 7.0, 0.0, 0.65)
    fg_probability = _clip(points_per_drive * 0.38 / 3.0, 0.0, 0.65)

    # Keep the probability of scoring on a drive below 1.
    if td_probability + fg_probability > 0.90:
        scale = 0.90 / (td_probability + fg_probability)
        td_probability *= scale
        fg_probability *= scale

    return td_probability, fg_probability


def _game_script_multiplier(score_margin):
    """Adjust offensive scoring efficiency for the team currently driving.

    Positive margin means that team is leading; negative means it is trailing.
    """
    if score_margin >= 14:
        return 0.88
    if score_margin >= 7:
        return 0.94
    if score_margin <= -14:
        return 1.10
    if score_margin <= -7:
        return 1.05
    return 1.00


def _score_one_drive(
    rng,
    expected_points,
    drives,
    efficiency,
    script_multiplier,
):
    """Return 0, 3, or 7 points for one simplified offensive drive."""
    adjusted_points = expected_points * script_multiplier
    td_probability, fg_probability = _drive_outcomes(
        adjusted_points, drives, efficiency
    )

    draw = rng.random()
    if draw < td_probability:
        return 7
    if draw < td_probability + fg_probability:
        return 3
    return 0


def _validate_inputs(home_mean, away_mean, spread, total, trials):
    for name, value in (
        ("home_mean", home_mean),
        ("away_mean", away_mean),
        ("spread", spread),
        ("total", total),
    ):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError(f"{name} must be a finite number.")

    if home_mean < 0 or away_mean < 0:
        raise ValueError("Expected team points cannot be negative.")
    if not isinstance(trials, int) or isinstance(trials, bool) or trials < 1:
        raise ValueError("Trials must be a positive integer.")


def simulate_drive_game(
    home_mean,
    away_mean,
    spread,
    total,
    trials=100000,
    seed=42,
    first_half=False,
):
    """Return simulated win, cover, total, and average-score probabilities."""
    _validate_inputs(home_mean, away_mean, spread, total, trials)
    rng = random.Random(seed)

    keys = (
        "home_win", "away_win", "tie",
        "home_cover", "away_cover", "spread_push",
        "over", "under", "total_push",
    )
    counts = dict.fromkeys(keys, 0)
    home_score_sum = 0
    away_score_sum = 0
    home_score_sq_sum = 0
    away_score_sq_sum = 0

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
            pace + rng.choice((-1, 0, 0, 1)), min_drives, max_drives
        ))
        away_drives = int(_clip(
            pace + rng.choice((-1, 0, 0, 1)), min_drives, max_drives
        ))

        # Shared game-level pace/efficiency uncertainty is sampled once per team.
        home_efficiency = _clip(rng.gauss(1.0, 0.10), 0.70, 1.30)
        away_efficiency = _clip(rng.gauss(1.0, 0.10), 0.70, 1.30)

        # Interleave possessions so score-dependent game script can take effect.
        drive_order = ["home"] * home_drives + ["away"] * away_drives
        rng.shuffle(drive_order)
        home = 0
        away = 0

        for offense in drive_order:
            if offense == "home":
                margin = home - away
                home += _score_one_drive(
                    rng, home_target, home_drives, home_efficiency,
                    _game_script_multiplier(margin),
                )
            else:
                margin = away - home
                away += _score_one_drive(
                    rng, away_target, away_drives, away_efficiency,
                    _game_script_multiplier(margin),
                )

        margin = home - away
        game_total = home + away
        home_score_sum += home
        away_score_sum += away
        home_score_sq_sum += home * home
        away_score_sq_sum += away * away

        if margin > 0:
            counts["home_win"] += 1
        elif margin < 0:
            counts["away_win"] += 1
        else:
            counts["tie"] += 1

        # spread is the home team's handicap: -3.5 requires a 4+ point win.
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
    results["home_score_sd"] = math.sqrt(max(
        0.0, home_score_sq_sum / trials - results["home_avg"] ** 2
    ))
    results["away_score_sd"] = math.sqrt(max(
        0.0, away_score_sq_sum / trials - results["away_avg"] ** 2
    ))
    results["mean_total"] = results["home_avg"] + results["away_avg"]
    results["mean_margin"] = results["home_avg"] - results["away_avg"]
    results["trials"] = trials
    results["first_half"] = bool(first_half)
    return results
