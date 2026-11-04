# Doug's Elite NBA Simulator

A team-level NBA forecasting and betting-analysis engine. It is separate from the NFL simulator.

## Included model features
- Matchup pace estimate and offensive rating versus opposing defensive rating.
- NBA Four Factors: effective field-goal percentage, turnover rate, offensive rebounding rate and free-throw rate, plus opponent-side factors.
- Full-season statistics blended with the prior season using an eight-game prior weight.
- Recent 10-game offensive/defensive rating and pace, shrunk 30% toward the season baseline.
- Home/road offensive and defensive ratings, shrunk toward the full-season baseline when venue samples are small.
- Schedule adjustments for rest, back-to-backs and travel distance.
- Team-level injury/availability point adjustments supplied as explicit inputs; the simulator does not pretend to verify injuries automatically.
- Correlated full-game and first-half Monte Carlo score distributions.
- Spread and total probabilities, pushes, projected score, projected margin, projected total, and model-vs-line edge.
- 1,000,000 baseline trials; borderline matchups refine to 5,000,000 trials.
- Fixed seeds and machine-readable JSON output for auditability.
- Betting leans require both at least 55% model probability and at least 1.5 points of model line edge. Otherwise the output is PASS.
- Historical evaluation utility reports point MAE, margin/total MAE, Brier score, log loss, calibration buckets, hit rates and optional closing-line movement.

## User-specific output scope
This is team-level only: no player-prop projections, player-prop data pipeline or moneyline recommendations. Betting outputs are spreads and game totals, full game and first half. No alternate spreads are created.

## Refresh data
Run the **Update NBA Statistics** workflow. It requests NBA.com Stats Advanced and Four Factors data for the current and prior seasons, plus current-season last-10 and home/road splits. The updater validates all 30 teams and writes only after every request and data check succeeds. It retries temporary request failures and preserves the last good file if a refresh fails.

The scheduled updater uses the 2026-27 season and 2025-26 as the prior baseline. Confirm the season settings when a new season begins. NBA Stats can rate-limit hosted runners; a failed refresh is not silently treated as current data.

## Run on GitHub
1. Open Actions.
2. Run **Update NBA Statistics** and confirm it completes successfully.
3. Run **Run Doug's Elite NBA Simulator**.
4. Enter home/away abbreviations, sportsbook home spread and total, rest days, approximate travel miles, and manual team-level injury point adjustments.
5. Keep the default 1,000,000 trials. The engine increases borderline runs to 5,000,000.
6. Download the text and JSON results artifact.

Spread convention: enter the home team's sportsbook line (for example, -4.5 when the home team is favored). Enter only the actual market line; no alternate line recommendations are generated.

## Run locally
```bash
python -m pip install numpy
python -m unittest -v nba.test_simulator nba.test_backtest
python -m nba.simulator --home BOS --away NYK --spread -3.5 --total 221.5 --trials 1000000
```

## Historical validation
Build a CSV of archived pregame predictions and final scores with the columns described in `nba/backtest.py`. Run:
```bash
python -m nba.backtest --csv nba/historical_predictions.csv
```
Do not call the model calibrated until it has enough chronologically separated out-of-sample games and its calibration, Brier score, log loss, MAE and closing-line value have been reviewed. The backtest script evaluates data supplied to it; it does not fabricate historical predictions or results.

## Known limitations
- Team-level injury point adjustments are manual. No official inactive/lineup feed is currently integrated.
- Schedule rest and travel are inputs; they are not yet fetched and verified automatically from the NBA schedule.
- No live sportsbook line ingestion, player rotations, player props, or play-by-play possession simulation.
- The score distribution is a transparent approximation pending fitting against historical game residuals. One million trials reduce Monte Carlo sampling noise; they do not correct bad inputs or model misspecification.
- Probabilities are estimates, not guaranteed outcomes or proof of a profitable betting edge.
