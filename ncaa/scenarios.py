"""Sensitivity scenarios for the NCAA simulator.

These are deterministic assumption stress tests, not injury reports or calibrated
probability distributions. They show how projections move under transparent
team-efficiency and pace changes.
"""
from __future__ import annotations

from dataclasses import replace
from .engine import MarketLines, TeamProfile, simulate_game


def run_sensitivity_scenarios(
    home: TeamProfile,
    away: TeamProfile,
    trials: int,
    lines: MarketLines | None = None,
    seed: int = 20261104,
    neutral_site: bool = False,
) -> dict:
    scenarios = {
        "baseline": (1.0, 1.0, 1.0),
        "home_offense_down_10pct": (0.90, 1.0, 1.0),
        "away_offense_down_10pct": (1.0, 0.90, 1.0),
        "both_offenses_down_10pct": (0.90, 0.90, 1.0),
        "slow_pace_down_8pct": (1.0, 1.0, 0.92),
        "fast_pace_up_8pct": (1.0, 1.0, 1.08),
    }
    output = {}
    for index, (name, (home_eff, away_eff, pace)) in enumerate(scenarios.items()):
        h = replace(
            home,
            points_for=max(1.0, home.points_for * home_eff),
            yards_per_play=max(1.0, home.yards_per_play * home_eff),
            yards_per_pass_attempt=max(0.1, home.yards_per_pass_attempt * home_eff),
            yards_per_carry=max(0.1, home.yards_per_carry * home_eff),
            plays_per_game=max(40.0, min(100.0, home.plays_per_game * pace)),
        )
        a = replace(
            away,
            points_for=max(1.0, away.points_for * away_eff),
            yards_per_play=max(1.0, away.yards_per_play * away_eff),
            yards_per_pass_attempt=max(0.1, away.yards_per_pass_attempt * away_eff),
            yards_per_carry=max(0.1, away.yards_per_carry * away_eff),
            plays_per_game=max(40.0, min(100.0, away.plays_per_game * pace)),
        )
        result = simulate_game(
            h, a, trials, lines=lines, seed=seed + index,
            neutral_site=neutral_site,
        )
        output[name] = {
            "assumptions": {
                "home_offense_scale": home_eff,
                "away_offense_scale": away_eff,
                "both_teams_pace_scale": pace,
            },
            "projected_score": result["projected_score"],
            "projected_total": result["projected_total"],
            "home_win_probability": result["home_win_probability"],
            "away_win_probability": result["away_win_probability"],
            "market": result["market"],
        }
    return {
        "interpretation": "Sensitivity analysis only; scenarios are not weighted or calibrated.",
        "scenarios": output,
    }
