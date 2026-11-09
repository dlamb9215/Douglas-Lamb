"""Elite NBA player-prop and market utilities.

Requires explicit, pregame player inputs. It never infers a player's availability,
minutes, role, or matchup adjustment from missing data. Experimental projections
must be backtested before being treated as betting edges.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np

VALID_STAT_KEYS = ("points", "rebounds", "assists")
BLOCKED_STATUSES = {"out", "doubtful", "questionable", "inactive", "suspended", "unknown"}


@dataclass(frozen=True)
class PlayerInput:
    player: str
    team: str
    status: str
    lineup_confirmed: bool
    minutes: float
    minutes_sd: float
    points_per_minute: float
    rebounds_per_minute: float
    assists_per_minute: float
    usage_multiplier: float = 1.0
    pace_multiplier: float = 1.0
    points_matchup_multiplier: float = 1.0
    rebounds_matchup_multiplier: float = 1.0
    assists_matchup_multiplier: float = 1.0

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PlayerInput":
        required = ("player", "team", "status", "lineup_confirmed", "minutes",
                    "minutes_sd", "points_per_minute", "rebounds_per_minute",
                    "assists_per_minute")
        missing = [key for key in required if key not in raw or raw[key] is None]
        if missing:
            raise ValueError("Missing player inputs: " + ", ".join(missing))
        p = cls(
            player=str(raw["player"]).strip(), team=str(raw["team"]).upper(),
            status=str(raw["status"]).strip().lower(),
            lineup_confirmed=bool(raw["lineup_confirmed"]),
            minutes=float(raw["minutes"]), minutes_sd=float(raw["minutes_sd"]),
            points_per_minute=float(raw["points_per_minute"]),
            rebounds_per_minute=float(raw["rebounds_per_minute"]),
            assists_per_minute=float(raw["assists_per_minute"]),
            usage_multiplier=float(raw.get("usage_multiplier", 1.0)),
            pace_multiplier=float(raw.get("pace_multiplier", 1.0)),
            points_matchup_multiplier=float(raw.get("points_matchup_multiplier", 1.0)),
            rebounds_matchup_multiplier=float(raw.get("rebounds_matchup_multiplier", 1.0)),
            assists_matchup_multiplier=float(raw.get("assists_matchup_multiplier", 1.0)),
        )
        if not p.player or not p.team:
            raise ValueError("Player name and team are required")
        if p.minutes <= 0 or p.minutes > 48 or p.minutes_sd < 0 or p.minutes_sd > 15:
            raise ValueError("Minutes must be 0-48 and minutes_sd 0-15")
        for key in ("points_per_minute", "rebounds_per_minute", "assists_per_minute"):
            if getattr(p, key) < 0 or getattr(p, key) > 3:
                raise ValueError(f"{key} outside plausible range")
        for key in ("usage_multiplier", "pace_multiplier", "points_matchup_multiplier",
                    "rebounds_matchup_multiplier", "assists_matchup_multiplier"):
            value = getattr(p, key)
            if not 0.5 <= value <= 1.5:
                raise ValueError(f"{key} must be between 0.5 and 1.5")
        return p

    def eligible(self) -> tuple[bool, str]:
        if self.status in BLOCKED_STATUSES:
            return False, f"status={self.status}"
        if self.status not in {"available", "probable"}:
            return False, f"unrecognized status={self.status}"
        if not self.lineup_confirmed:
            return False, "lineup not confirmed"
        if self.minutes < 8 or self.minutes_sd > 8:
            return False, "minutes projection is too uncertain"
        return True, "eligible"


def _normal_counts(rng, mean, sd, n):
    return np.maximum(0.0, rng.normal(mean, max(sd, 0.05), n))


def simulate_player_props(raw: dict[str, Any] | PlayerInput, trials: int = 200_000,
                          seed: int = 42, lines: dict[str, float] | None = None) -> dict[str, Any]:
    """Simulate points/rebounds/assists/PRA with shared minutes and game shocks.

    Inputs are per-minute production rates and projected minutes. This is an
    experimental distribution model, not a replacement for a fitted player model.
    """
    player = raw if isinstance(raw, PlayerInput) else PlayerInput.from_dict(raw)
    eligible, reason = player.eligible()
    if not eligible:
        return {"player": player.player, "team": player.team, "eligible": False,
                "reason": reason, "projections": {}}
    if trials < 1:
        raise ValueError("trials must be positive")
    rng = np.random.default_rng(seed)
    minutes = np.clip(rng.normal(player.minutes, player.minutes_sd, trials), 0, 48)
    shared = rng.normal(0, 0.035, trials)
    pace = np.clip(1 + shared + rng.normal(0, 0.015, trials), 0.85, 1.15)
    factors = {
        "points": player.points_per_minute * player.usage_multiplier * player.points_matchup_multiplier,
        "rebounds": player.rebounds_per_minute * player.rebounds_matchup_multiplier,
        "assists": player.assists_per_minute * player.usage_multiplier * player.assists_matchup_multiplier,
    }
    # Rate variance grows with expected count; shared minutes and pace correlate stats.
    values = {}
    for stat, rate in factors.items():
        mean = minutes * rate * player.pace_multiplier * pace
        sd = np.sqrt(np.maximum(mean, 0.25) * (1.0 + (0.12 if stat == "points" else 0.18) ** 2 * mean))
        values[stat] = _normal_counts(rng, mean, sd, trials)
    values["pra"] = values["points"] + values["rebounds"] + values["assists"]
    output = {}
    for stat, samples in values.items():
        row = {"mean": float(np.mean(samples)), "median": float(np.median(samples)),
               "p10": float(np.quantile(samples, .10)), "p90": float(np.quantile(samples, .90))}
        line = (lines or {}).get(stat)
        if line is not None:
            row.update({"line": float(line),
                        "over_probability": float(np.mean(samples > float(line)) * 100),
                        "under_probability": float(np.mean(samples < float(line)) * 100),
                        "push_probability": float(np.mean(samples == float(line)) * 100)})
        output[stat] = row
    return {"player": player.player, "team": player.team, "eligible": True,
            "trials": trials, "seed": seed, "projections": output,
            "warning": "Experimental rate/minutes model; requires player-level historical backtesting and verified inputs."}


def american_implied_probability(odds: int | float) -> float:
    odds = float(odds)
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def no_vig_two_way(over_odds: int | float, under_odds: int | float) -> dict[str, float]:
    over = american_implied_probability(over_odds)
    under = american_implied_probability(under_odds)
    total = over + under
    return {"over": over / total * 100, "under": under / total * 100,
            "hold_pct": (total - 1) * 100}


def expected_value_per_100(probability_pct: float, american_odds: int | float) -> float:
    """Expected net dollars per $100 risked; probability is percentage 0-100."""
    p = float(probability_pct) / 100
    if not 0 <= p <= 1:
        raise ValueError("probability_pct must be 0-100")
    odds = float(american_odds)
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    profit = odds if odds > 0 else 10000 / abs(odds)
    return p * profit - (1 - p) * 100


def scenario_grid(base: dict[str, float], scenarios: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Apply explicit scenario deltas to a baseline projection, preserving provenance."""
    result = {"baseline": dict(base)}
    for name, changes in scenarios.items():
        if not name or name == "baseline":
            raise ValueError("Scenario names must be non-empty and cannot be baseline")
        unknown = set(changes) - set(base)
        if unknown:
            raise ValueError(f"Unknown scenario fields: {', '.join(sorted(unknown))}")
        result[name] = {key: float(value) + float(changes.get(key, 0))
                        for key, value in base.items()}
    return result
