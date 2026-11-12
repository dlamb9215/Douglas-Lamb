# Unified NBA + NFL Betting Decision Engine

The shared, conservative decision layer at `betting_engine/` is now wired into
the NBA team-market CLI, NFL team-market CLI, NBA player-prop ranking, and NFL
player-prop pipeline. It consumes each sport model's probabilities and actual
two-sided prices; it does not replace either scoring engine.

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

## Integration behavior
- NBA and NFL game markets are evaluated through the same two-way market adapter.
- NFL spread markets require both home and away spread prices; NFL moneyline and total markets require both sides.
- NBA no longer assumes default -110 prices. A market comparison needs two actual prices and a timestamped sportsbook/provider quote.
- NBA team-market availability requires a fresh confirmed-lineup payload with five available starters per team plus a submitted official injury report for both teams.
- NFL player props flow through the shared engine only after the existing official active-starter confirmation gate passes.
- NBA player props flow through the shared engine only after the existing official injury and confirmed minutes/lineup gates pass.
- Each market report includes no-vig probability, breakeven probability, expected value, edge, quote age, and explicit blockers.

## Current limitations and release gates
The integration is end-to-end at the report/decision layer, but it is **not yet certified to issue BET recommendations**. Calibration remains deliberately false for NBA team markets, NBA player props, NFL team markets, and NFL player props until market-specific, time-ordered out-of-sample ledgers meet the review standard. NFL team markets also remain blocked until the team-level official inactive/starter confirmation is wired and attested. Do not manually set calibration flags true or treat green CI as proof of predictive accuracy.

Automatic sportsbook coverage depends on configured providers/API keys. The NBA Odds API and ESPN BET adapters may return no prices for an event; missing prices remain PASS. NFL market prices are entered as a timestamped two-sided snapshot. Never infer a market price from the usual -110 convention.

Do not describe any output as profitable or validated until the historical ledger has enough settled, chronologically separated observations and calibration/ROI/closing-line-value reviews are satisfactory.
