"""Conservative MLB 1+ hit model primitives.

This first release is a transparent baseline. It requires a source-verified
confirmed lineup and uses season hit/plate-appearance rates with shrinkage.
It is not betting-approved until matchup features and market-specific
chronological calibration are implemented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
import random
from typing import Any

LEAGUE_HIT_PER_PA_PRIOR = 0.23
BATTER_PRIOR_PA = 50.0
PITCHER_PRIOR_BF = 100.0
DEFAULT_PA_BY_ORDER = {
    1: 4.60, 2: 4.45, 3: 4.35, 4: 4.25, 5: 4.15,
    6: 4.05, 7: 3.95, 8: 3.85, 9: 3.75,
}


def _finite_nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return value


def validate_confirmed_lineup(payload: dict, game_pk: int, *, now=None,
                               max_age_hours: float = 3.0) -> dict:
    """Validate a manually verified official game-day lineup snapshot.

    The caller must provide an official source URL and timezone-aware check
    time. Each side must have batting orders 1-9 and a confirmed starter ID.
    """
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        raise ValueError("confirmed official lineups are required")
    if int(payload.get("gamePk", -1)) != int(game_pk):
        raise ValueError("lineup gamePk does not match the selected game")
    source = str(payload.get("source_url", "")).strip()
    if not source.startswith("https://"):
        raise ValueError("an HTTPS official lineup source_url is required")
    checked = str(payload.get("checked_at_utc", "")).strip()
    if not checked:
        raise ValueError("checked_at_utc is required")
    stamp = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("checked_at_utc must include a timezone")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    age = (current.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600
    if age < 0 or age > max_age_hours:
        raise ValueError("confirmed lineup snapshot is future-dated or older than 3 hours")
    teams = payload.get("teams")
    if not isinstance(teams, dict) or not {"home", "away"}.issubset(teams):
        raise ValueError("both home and away lineup objects are required")
    normalized = {}
    for side in ("home", "away"):
        team = teams[side]
        players = team.get("batters") if isinstance(team, dict) else None
        if not isinstance(players, list) or len(players) != 9:
            raise ValueError(f"{side} lineup must contain exactly nine confirmed batters")
        orders = []
        ids = []
        for player in players:
            pid = player.get("player_id")
            order = player.get("batting_order")
            if not isinstance(pid, int) or pid <= 0:
                raise ValueError(f"{side} lineup contains an invalid player_id")
            if not isinstance(order, int) or order < 1 or order > 9:
                raise ValueError(f"{side} lineup contains an invalid batting_order")
            ids.append(pid)
            orders.append(order)
        if sorted(orders) != list(range(1, 10)) or len(set(ids)) != 9:
            raise ValueError(f"{side} lineup must have unique players and batting orders 1-9")
        pitcher_id = team.get("starting_pitcher_id")
        if not isinstance(pitcher_id, int) or pitcher_id <= 0:
            raise ValueError(f"{side} confirmed starting_pitcher_id is required")
        normalized[side] = {"batters": sorted(players, key=lambda x: x["batting_order"]),
                            "starting_pitcher_id": pitcher_id}
    return {"gamePk": int(game_pk), "source_url": source, "checked_at_utc": stamp.isoformat(),
            "lineup_age_hours": round(age, 2), "teams": normalized}


def shrunk_batter_hit_rate(hits: float, plate_appearances: float) -> float:
    h = _finite_nonnegative(hits, "hits")
    pa = _finite_nonnegative(plate_appearances, "plate_appearances")
    if pa <= 0 or h > pa:
        raise ValueError("batter hits must be between zero and positive plate appearances")
    return (h + LEAGUE_HIT_PER_PA_PRIOR * BATTER_PRIOR_PA) / (pa + BATTER_PRIOR_PA)


def shrunk_pitcher_hit_rate(hits_allowed: float, batters_faced: float) -> float:
    h = _finite_nonnegative(hits_allowed, "hits_allowed")
    bf = _finite_nonnegative(batters_faced, "batters_faced")
    if bf <= 0 or h > bf:
        raise ValueError("pitcher hits allowed must be between zero and positive batters faced")
    return (h + LEAGUE_HIT_PER_PA_PRIOR * PITCHER_PRIOR_BF) / (bf + PITCHER_PRIOR_BF)


def project_one_plus_hit(*, batter_hits: float, batter_pa: float,
                         pitcher_hits_allowed: float, pitcher_bf: float,
                         batting_order: int, projected_pa: float | None = None) -> dict:
    """Return a shrunk, pitcher-adjusted baseline 1+ hit probability."""
    if batting_order not in DEFAULT_PA_BY_ORDER:
        raise ValueError("batting_order must be 1 through 9")
    batter_rate = shrunk_batter_hit_rate(batter_hits, batter_pa)
    pitcher_rate = shrunk_pitcher_hit_rate(pitcher_hits_allowed, pitcher_bf)
    # Conservative 70/30 blend on the rate scale; not yet handedness adjusted.
    hit_rate = 0.70 * batter_rate + 0.30 * pitcher_rate
    pa = _finite_nonnegative(projected_pa if projected_pa is not None
                             else DEFAULT_PA_BY_ORDER[batting_order], "projected_pa")
    if pa <= 0 or pa > 8:
        raise ValueError("projected_pa must be greater than zero and no more than eight")
    probability = 1.0 - (1.0 - hit_rate) ** pa
    return {
        "batter_hit_per_pa_shrunk": round(batter_rate, 5),
        "opposing_pitcher_hit_allowed_per_bf_shrunk": round(pitcher_rate, 5),
        "blended_hit_per_pa": round(hit_rate, 5),
        "projected_plate_appearances": round(pa, 2),
        "one_plus_hit_probability": round(probability, 5),
        "one_plus_hit_pct": round(probability * 100, 2),
        "model_status": "BASELINE_ONLY_NOT_CALIBRATED",
    }


def simulate_one_plus_hit(hit_rate_per_pa: float, projected_pa: float,
                          trials: int = 500_000, seed: int = 20261117) -> dict:
    """Monte Carlo check of the closed-form 1+ hit probability."""
    rate = _finite_nonnegative(hit_rate_per_pa, "hit_rate_per_pa")
    pa = _finite_nonnegative(projected_pa, "projected_pa")
    if not 0 < rate < 1 or not 0 < pa <= 8:
        raise ValueError("rate must be between 0 and 1 and PA must be in (0, 8]")
    if not isinstance(trials, int) or trials < 1000:
        raise ValueError("trials must be an integer of at least 1,000")
    rng = random.Random(seed)
    full_pa = int(pa)
    fractional_pa = pa - full_pa
    hits = 0
    for _ in range(trials):
        has_hit = any(rng.random() < rate for _ in range(full_pa))
        if not has_hit and fractional_pa > 0:
            has_hit = rng.random() < (1.0 - (1.0 - rate) ** fractional_pa)
        if has_hit:
            hits += 1
    return {"trials": trials, "seed": seed,
            "simulated_probability": hits / trials,
            "analytic_probability": 1 - (1-rate) ** pa}
