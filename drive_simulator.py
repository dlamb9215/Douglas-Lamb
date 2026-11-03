"""Drive-based NFL scoring simulation for Doug's Elite Game Simulator.

This is a possession-level approximation, not a play-by-play model.
The spread argument is the home team's handicap (e.g. -3 means home -3).
"""
import random


def _clip(value, low, high):
    return max(low, min(high, value))


def _drive_outcomes(points_per_game, drives, efficiency=1.0):
    """Convert a scoring mean into mutually exclusive TD/FG/empty drives."""
    points_per_drive = max(0.0, points_per_game * efficiency / max(1, drives))
    td_probability = _clip(points_per_drive * 0.62 / 7.0, 0.0, 0.65)
    fg_probability = _clip(points_per_drive * 0.38 / 3.0, 0.0, 0.65)

    if td_probability + fg_probability > 0.90:
        scale = 0.90 / (td_probability + fg_probability)
        td_probability *= scale
        fg_probability *= scale

    return td_probability, fg_probability


def _game_script_multiplier(score_margin):
    """Simple trailing/leading adjustment; bounded to avoid runaway feedback."""
    if score_margin >= 14:
        return 0.88
    if score_margin >= 7:
        return 0.94
    if score_margin <= -14:
        return 1.10
    if score_margin <= -7:
        return 1.05
    return 1.00


def _score_one_drive(rng, expected_points, drives, efficiency, script_multiplier):
    adjusted_points = max(0.0, expected_points * script_multiplier)
    td_probability, fg_probability = _drive_outcomes(
        adjusted_points, drives, efficiency
    )
    draw = rng.random()
    if draw < td_probability:
        return 7
    if draw < td_probability + fg_probability:
        return 3
    return 0


def _validate_inputs(home_mean, away_mean, spread, total, trials, home_sd, away_sd):
    for label, value in (
        ("home_mean", home_mean), ("away_mean", away_mean),
        ("spread", spread), ("total", total),
        ("home_sd", home_sd), ("away_sd", away_sd),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{label} must be numeric.")
    if home_mean < 0 or away_mean < 0 or home_sd < 0 or away_sd < 0:
        raise ValueError("Scoring means and standard deviations cannot be negative.")
    if trials < 1:
        raise ValueError("Trials must be greater than zero.")


def simulate_drive_game(
    home_mean,
    away_mean,
    spread,
    total,
    trials=100000,
    seed=42,
    first_half=False,
    home_sd=10.0,
    away_sd=10.0,
):
    """Return simulated win, cover, total and average-score probabilities."""
    _validate_inputs(home_mean, away_mean, spread, total, trials, home_sd, away_sd)
    rng = random.Random(seed)

    keys = (
        "home_win", "away_win", "tie", "home_cover", "away_cover",
        "spread_push", "over", "under", "total_push",
    )
    counts = dict.fromkeys(keys, 0)
    home_score_sum = 0
    away_score_sum = 0

    for _ in range(trials):
        if first_half:
            pace = int(_clip(round(rng.gauss(5.3, 0.8)), 3, 8))
            min_drives, max_drives = 3, 8
            home_target, away_target = home_mean / 2, away_mean / 2
        else:
            pace = int(_clip(round(rng.gauss(10.6, 1.2)), 7, 15))
            min_drives, max_drives = 7, 15
            home_target, away_target = home_mean, away_mean

        home_drives = int(_clip(pace + rng.choice((-1, 0, 0, 1)), min_drives, max_drives))
        away_drives = int(_clip(pace + rng.choice((-1, 0, 0, 1)), min_drives, max_drives))

        # Team-level game variance: standard deviations now affect outcomes.
        home_cv = _clip(home_sd / max(home_target, 10.0) * 0.35, 0.03, 0.30)
        away_cv = _clip(away_sd / max(away_target, 10.0) * 0.35, 0.03, 0.30)
        home_efficiency = _clip(rng.lognormvariate(-0.5 * home_cv**2, home_cv), 0.65, 1.40)
        away_efficiency = _clip(rng.lognormvariate(-0.5 * away_cv**2, away_cv), 0.65, 1.40)

        home = 0
        away = 0
        # Alternate possessions so score-state effects can influence later drives.
        for drive_index in range(max(home_drives, away_drives)):
            if drive_index < home_drives:
                margin = home - away
                home += _score_one_drive(
                    rng, home_target, home_drives, home_efficiency,
                    _game_script_multiplier(margin),
                )
            if drive_index < away_drives:
                margin = away - home
                away += _score_one_drive(
                    rng, away_target, away_drives, away_efficiency,
                    _game_script_multiplier(margin),
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

    results = {key: value * 100.0 / trials for key, value in counts.items()}
    results["home_avg"] = home_score_sum / trials
    results["away_avg"] = away_score_sum / trials
    return results
