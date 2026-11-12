"""Conservative sportsbook decision layer shared by NBA and NFL engines.

Consumes model probabilities and timestamped market quotes; it does not invent
lines, infer player availability, or treat Monte Carlo precision as calibration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable


@dataclass(frozen=True)
class BetCandidate:
    sport: str
    event: str
    market: str
    selection: str
    model_probability: float
    odds_american: int
    line: float | None = None
    opposite_odds_american: int | None = None
    push_probability: float = 0.0
    sportsbook: str = ""
    quoted_at: str = ""
    data_ready: bool = False
    availability_confirmed: bool = False
    calibration_ready: bool = False
    notes: str = ""


def implied_probability(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return (-odds / (-odds + 100)) if odds < 0 else (100 / (odds + 100))


def decimal_odds(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return 1 + (100 / -odds if odds < 0 else odds / 100)


def no_vig_probabilities(odds_a: int, odds_b: int) -> tuple[float, float]:
    a, b = implied_probability(odds_a), implied_probability(odds_b)
    total = a + b
    return a / total, b / total


def quote_age_hours(quoted_at: str, now: datetime | None = None) -> float:
    if not quoted_at:
        raise ValueError("A timezone-aware quote timestamp is required")
    stamp = datetime.fromisoformat(quoted_at.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Quote timestamp must include a timezone")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Current time must be timezone-aware")
    return (current.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600


def evaluate(candidate: BetCandidate, *, now: datetime | None = None,
             max_quote_age_hours: float = 6.0, min_edge: float = 0.025,
             min_ev_per_unit: float = 0.02, max_kelly_fraction: float = 0.05) -> dict[str, Any]:
    p, push = candidate.model_probability, candidate.push_probability
    if not isfinite(float(p)) or not isfinite(float(push)) or not 0 <= p <= 1 or not 0 <= push < 1 or p + push > 1:
        raise ValueError("Invalid model or push probability")
    if isinstance(candidate.odds_american, bool) or not isinstance(candidate.odds_american, (int, float)) or not isfinite(float(candidate.odds_american)) or candidate.odds_american == 0:
        raise ValueError("American odds must be a finite non-zero number")
    if not candidate.sport or candidate.sport.upper() not in {"NBA", "NFL"}:
        raise ValueError("sport must be NBA or NFL")
    if not candidate.sportsbook:
        raise ValueError("Sportsbook/source is required")
    age = quote_age_hours(candidate.quoted_at, now)
    if age < 0 or age > max_quote_age_hours:
        raise ValueError("Market quote is future-dated or stale")
    dec = decimal_odds(candidate.odds_american)
    win_profit = dec - 1
    # Expected profit per unit staked; push returns stake.
    ev = p * win_profit - (1 - p - push)
    breakeven = (1 - push) / dec
    edge = p - breakeven
    # Kelly for a market with push probability; conservative approximation
    # uses non-push conditional probability and caps stake at 5% bankroll.
    nonpush = 1 - push
    conditional_p = p / nonpush if nonpush else 0.0
    b = win_profit
    raw_kelly = max(0.0, (b * conditional_p - (1 - conditional_p)) / b) if b > 0 else 0.0
    kelly = min(raw_kelly, max_kelly_fraction)
    blockers = []
    if not candidate.data_ready: blockers.append("required data readiness gate failed")
    if not candidate.availability_confirmed: blockers.append("official availability/lineup confirmation missing")
    if not candidate.calibration_ready: blockers.append("out-of-sample calibration gate not passed")
    if edge < min_edge: blockers.append("model edge below threshold")
    if ev < min_ev_per_unit: blockers.append("expected value below threshold")
    result = {
        **asdict(candidate),
        "quote_age_hours": round(age, 2),
        "decimal_odds": round(dec, 4),
        "raw_implied_probability": round(implied_probability(candidate.odds_american), 4),
        "no_vig_market_probability": None,
        "breakeven_probability": round(breakeven, 4),
        "model_edge": round(edge, 4),
        "expected_value_per_unit": round(ev, 4),
        "expected_roi_percent": round(ev * 100, 2),
        "capped_kelly_fraction": round(kelly, 4),
        "decision": "BET" if not blockers else "PASS",
        "blockers": blockers,
    }
    if candidate.opposite_odds_american is not None:
        result = attach_no_vig_market(result, candidate.opposite_odds_american)
    return result


def rank_candidates(candidates: Iterable[BetCandidate], **kwargs: Any) -> list[dict[str, Any]]:
    results = []
    for candidate in candidates:
        try:
            results.append(evaluate(candidate, **kwargs))
        except (ValueError, TypeError) as exc:
            results.append({**asdict(candidate), "decision": "PASS",
                            "blockers": [str(exc)]})
    return sorted(results, key=lambda x: (
        x["decision"] == "BET",
        x.get("expected_value_per_unit", float("-inf")),
        x.get("model_edge", float("-inf")),
    ), reverse=True)


def attach_no_vig_market(result: dict[str, Any], opposite_odds: int) -> dict[str, Any]:
    """Add a two-way no-vig market probability when both sides are available."""
    a, b = no_vig_probabilities(int(result["odds_american"]), opposite_odds)
    result["no_vig_market_probability"] = round(a, 4)
    result["no_vig_opposite_probability"] = round(b, 4)
    result["edge_vs_no_vig_market"] = round(result["model_probability"] - a, 4)
    return result
