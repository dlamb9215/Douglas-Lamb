# Unified NBA + NFL Betting Decision Engine

This branch adds a shared, conservative decision layer at `betting_engine/`.
It is designed to consume probabilities and prices produced by the existing
sport-specific simulators; it does not replace either scoring engine.

## Decision outputs
- American odds converted to implied and decimal odds.
- Two-way no-vig probability helper.
- Breakeven probability, model edge, expected value per unit and expected ROI.
- Push-aware EV for spread/total markets.
- Capped fractional Kelly sizing indicator (maximum 5% of bankroll; informational).
- Quote age validation; missing, timezone-naive, future-dated or >6-hour quotes fail closed.
- BET/PASS ranking with explicit blockers.

## Required gates
A candidate is PASS unless all are true:
1. Current data readiness is explicitly true.
2. Official player availability/lineup confirmation is explicitly true (for team markets, the caller must attest that relevant starters/inactives were checked).
3. Out-of-sample calibration readiness is explicitly true.
4. Model edge is at least 2.5 percentage points over breakeven.
5. Expected value is at least 2% of stake.
6. Sportsbook/source and a timezone-aware quote timestamp are supplied and no older than six hours.

These are conservative starting thresholds, not proof of profitability. The
calibration flag must be earned from a chronologically held-out sample, not
set true merely because tests pass or simulations complete.

## Integration contract
NBA and NFL callers should map each model market to `BetCandidate` and pass
the model probability, actual current book price, push probability, source,
timestamp and readiness gates. Never fabricate a line or infer a confirmed
starter from a roster/depth chart feed. Player props remain blocked without
official game-day availability and game-specific role/minutes/workload inputs.

## Run tests
```bash
python -m unittest -v betting_engine.test_decision
```

## Current limitations
This shared layer is a tested foundation, not a completed end-to-end integration.
The existing NBA player-prop model remains experimental and the NFL player-prop
workflow still requires official confirmation files. Automatic sportsbook
coverage depends on configured providers/API keys. Do not describe picks as
validated or profitable until the historical ledger has enough settled,
chronologically separated observations and calibration/ROI/closing-line-value
reviews are satisfactory.
