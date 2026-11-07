"""Manual-input player workload and prop Monte Carlo layer.

Player inputs must be sourced and current. The module does not scrape rosters,
infer availability, or model correlations between teammates.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path


def _finite(value, label, minimum=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{label} must be finite and >= {minimum}")
    return number


def load_player_inputs(path: str | Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Player input file must contain a JSON list")
    seen = set()
    players = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each player entry must be an object")
        name = str(item.get("player", "")).strip()
        team = str(item.get("team", "")).strip()
        role = str(item.get("role", "")).strip().upper()
        if not name or not team:
            raise ValueError("Each player requires player and team")
        if role not in {"QB", "RB", "WR", "TE"}:
            raise ValueError(f"{name}: role must be QB, RB, WR, or TE")
        key = (name.casefold(), team.casefold())
        if key in seen:
            raise ValueError(f"Duplicate player entry: {name}")
        seen.add(key)
        opportunities = _finite(item.get("expected_opportunities"), f"{name} expected_opportunities")
        success = _finite(item.get("success_probability"), f"{name} success_probability")
        if success > 1:
            raise ValueError(f"{name}: success_probability must be <= 1")
        yards = _finite(item.get("yards_per_success"), f"{name} yards_per_success")
        yards_sd = _finite(item.get("yards_sd_per_success", 0), f"{name} yards_sd_per_success")
        td_rate = _finite(item.get("touchdown_rate_per_opportunity", 0), f"{name} touchdown_rate_per_opportunity")
        if td_rate > 1:
            raise ValueError(f"{name}: touchdown_rate_per_opportunity must be <= 1")
        if not item.get("source") or not item.get("as_of"):
            raise ValueError(f"{name}: source and as_of are required")
        players.append({
            "player": name, "team": team, "role": role,
            "expected_opportunities": opportunities,
            "success_probability": success,
            "yards_per_success": yards,
            "yards_sd_per_success": yards_sd,
            "touchdown_rate_per_opportunity": td_rate,
            "source": str(item["source"]),
            "as_of": str(item["as_of"]),
        })
    return players


def _poisson(mean: float, rng: random.Random) -> int:
    # Knuth sampler is stable for modest per-game workloads.
    if mean <= 0:
        return 0
    limit = math.exp(-mean)
    product = 1.0
    count = 0
    while product > limit:
        count += 1
        product *= rng.random()
    return count - 1


def simulate_player(player: dict, trials: int = 100_000, seed: int = 20261104,
                    prop_lines: dict | None = None) -> dict:
    if trials < 1 or trials > 5_000_000:
        raise ValueError("trials must be between 1 and 5,000,000")
    rng = random.Random(seed)
    opportunity_counts, successes, yards, touchdowns = [], [], [], []
    for _ in range(trials):
        count = _poisson(player["expected_opportunities"], rng)
        made = sum(rng.random() < player["success_probability"] for _ in range(count))
        total_yards = sum(max(0.0, rng.gauss(
            player["yards_per_success"], player["yards_sd_per_success"]
        )) for _ in range(made))
        td = sum(rng.random() < player["touchdown_rate_per_opportunity"]
                 for _ in range(count))
        opportunity_counts.append(count)
        successes.append(made)
        yards.append(total_yards)
        touchdowns.append(td)
    lines = {}
    for market, values in (prop_lines or {}).items():
        if market not in {"yards", "opportunities", "successes", "touchdowns"}:
            raise ValueError(f"Unsupported player prop market: {market}")
        if not isinstance(values, (int, float)) or not math.isfinite(values):
            raise ValueError(f"{market} prop line must be finite")
        samples = {"yards": yards, "opportunities": opportunity_counts,
                   "successes": successes, "touchdowns": touchdowns}[market]
        over = sum(value > values for value in samples) / trials
        push = sum(value == values for value in samples) / trials
        lines[market] = {
            "line": values,
            "over_probability": round(over, 4),
            "under_probability": round(1 - over - push, 4),
            "push_probability": round(push, 4),
        }
    return {
        "player": player["player"], "team": player["team"], "role": player["role"],
        "trials": trials, "seed": seed,
        "expected_opportunities": round(sum(opportunity_counts) / trials, 2),
        "expected_successes": round(sum(successes) / trials, 2),
        "projected_yards": round(sum(yards) / trials, 2),
        "expected_touchdowns": round(sum(touchdowns) / trials, 3),
        "prop_probabilities": lines,
        "input_provenance": {"source": player["source"], "as_of": player["as_of"]},
        "warning": "Manual usage inputs; no live roster verification or teammate/game correlation.",
    }


def simulate_players(path: str | Path, trials: int = 100_000,
                     seed: int = 20261104) -> list[dict]:
    players = load_player_inputs(path)
    return [simulate_player(
        player, trials, seed + index, player.get("prop_lines", {})
    ) for index, player in enumerate(players)]
