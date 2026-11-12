"""Adapters that connect sport-specific model probabilities to the shared BET/PASS gate.

The adapter never supplies fallback prices or timestamps. Missing market data,
unconfirmed availability, or unearned calibration yields PASS.
"""
from __future__ import annotations

from typing import Any

from betting_engine.decision import BetCandidate, evaluate


def evaluate_two_way_market(
    *, sport: str, event: str, market: str, line: float | None,
    selection_a: str, probability_a: float, odds_a: int | float | None,
    selection_b: str, probability_b: float, odds_b: int | float | None,
    push_probability: float = 0.0, sportsbook: str = "", quoted_at: str = "",
    data_ready: bool = False, availability_confirmed: bool = False,
    calibration_ready: bool = False, notes: str = "",
    now=None,
) -> dict[str, Any]:
    """Evaluate both sides using one actual two-way quote snapshot."""
    if odds_a is None or odds_b is None:
        return {
            "sport": sport, "event": event, "market": market, "line": line,
            "decision": "PASS", "selections": [],
            "blockers": ["both current sportsbook prices are required; no fallback odds are assumed"],
        }

    selections = []
    for selection, probability, odds, opposite in (
        (selection_a, probability_a, odds_a, odds_b),
        (selection_b, probability_b, odds_b, odds_a),
    ):
        candidate = BetCandidate(
            sport=sport, event=event, market=market, selection=selection,
            model_probability=float(probability), odds_american=int(odds),
            line=line, opposite_odds_american=int(opposite),
            push_probability=float(push_probability), sportsbook=sportsbook,
            quoted_at=quoted_at, data_ready=data_ready,
            availability_confirmed=availability_confirmed,
            calibration_ready=calibration_ready, notes=notes,
        )
        try:
            result = evaluate(candidate, now=now)
        except (ValueError, TypeError, OverflowError) as exc:
            result = {
                "sport": sport, "event": event, "market": market,
                "selection": selection, "decision": "PASS",
                "blockers": [str(exc)],
            }
        selections.append(result)

    bets = [row for row in selections if row.get("decision") == "BET"]
    return {
        "sport": sport, "event": event, "market": market, "line": line,
        "sportsbook": sportsbook or None, "quoted_at": quoted_at or None,
        "decision": "BET" if bets else "PASS",
        "selections": selections,
        "blockers": [] if bets else sorted({reason for row in selections for reason in row.get("blockers", [])}),
    }


def evaluate_market_set(markets: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize a set of market evaluations without upgrading any PASS to BET."""
    rows = [row for row in markets if row]
    qualified = [
        {"market": row["market"], "selection": side["selection"],
         "expected_value_per_unit": side.get("expected_value_per_unit"),
         "model_edge": side.get("model_edge")}
        for row in rows for side in row.get("selections", [])
        if side.get("decision") == "BET"
    ]
    return {
        "markets": rows,
        "qualified_bets": qualified,
        "status": "BET_CANDIDATE" if qualified else "PASS_ALL_MARKETS",
    }
