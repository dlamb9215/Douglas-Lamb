"""Sportsbook odds utilities. Probabilities are descriptive, not betting advice."""
from __future__ import annotations
import math

def american_to_implied(odds: float) -> float:
    if not math.isfinite(odds) or odds == 0:
        raise ValueError("American odds must be finite and non-zero")
    return 100.0 / (odds + 100.0) if odds > 0 else -odds / (-odds + 100.0)

def remove_vig_two_way(odds_a: float, odds_b: float) -> dict:
    raw_a, raw_b = american_to_implied(odds_a), american_to_implied(odds_b)
    total = raw_a + raw_b
    return {"raw_implied_a": round(raw_a, 6), "raw_implied_b": round(raw_b, 6),
            "overround": round(total - 1.0, 6),
            "fair_probability_a": round(raw_a / total, 6),
            "fair_probability_b": round(raw_b / total, 6)}

def expected_value_per_100(model_probability: float, american_odds: float) -> float:
    if not math.isfinite(model_probability) or not 0 <= model_probability <= 1:
        raise ValueError("Model probability must be between 0 and 1")
    if not math.isfinite(american_odds) or american_odds == 0:
        raise ValueError("American odds must be finite and non-zero")
    profit = american_odds if american_odds > 0 else 10000.0 / -american_odds
    return round(model_probability * profit - (1.0 - model_probability) * 100.0, 2)
