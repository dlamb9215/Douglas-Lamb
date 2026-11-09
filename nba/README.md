# Doug's Elite NBA Simulator

A professional-style NBA forecasting and betting-analysis toolkit. The team engine and the experimental player-prop engine are separate so unsupported player inputs cannot contaminate team projections.

## Team engine
- Pace × opponent-adjusted offensive/defensive efficiency.
- NBA Four Factors: eFG%, turnover rate, offensive rebounding rate and free-throw rate.
- Prior-season shrinkage, recent form, home/road splits, 3-point shot profile, rest and travel adjustments when valid data is supplied.
- Full-game and first-half correlated Monte Carlo score distributions.
- 1,000,000-trial default; configurable up to 5,000,000 for close decisions.
- Spread and game-total probabilities, push rates, score/margin/total projections, model-line edge and Monte Carlo confidence intervals.
- Fixed seeds and JSON output for reproducibility.
- PASS-first decision rule: a lean requires both a minimum probability and minimum line edge. No alternate lines are generated.
- Injury point adjustments are explicit inputs; they must be sourced from verified player availability and impact analysis.

## Experimental player-prop engine
The new `nba/elite_analytics.py` module provides points, rebounds, assists and PRA distributions using supplied per-minute production rates, projected minutes, minutes uncertainty, usage and matchup multipliers. It also provides two-way no-vig conversion and expected value per $100 risked.

**Strict eligibility gate:** Out, doubtful, questionable, inactive, suspended or unknown players are excluded. A player must be explicitly marked available/probable, have a confirmed lineup, and have a sufficiently stable minutes projection. The code does not fetch or verify these facts automatically. It does not invent player inputs.

Run it with a verified JSON file:
```bash
python -m nba.player_props_cli --input player-projection.json --trials 200000
```
Example input schema:
```json
{
  "player": "Example Player",
  "team": "BOS",
  "status": "available",
  "lineup_confirmed": true,
  "minutes": 34,
  "minutes_sd": 2.5,
  "points_per_minute": 0.72,
  "rebounds_per_minute": 0.18,
  "assists_per_minute": 0.20,
  "lines": {"points": 24.5, "rebounds": 6.5, "assists": 5.5, "pra": 36.5}
}
```
These player distributions are an experimental baseline, not yet a calibrated betting model. Do not use them as recommendations until the player game-log pipeline, rotation/minutes projections, injury/lineup feed, and out-of-sample prop backtests have been completed.

## Data pipeline and freshness
Run **Update NBA Statistics** before a slate. The updater requests NBA.com Stats current/prior season advanced and Four Factors data, recent form, venue splits and game-log variance; it validates all teams before replacing the last-good file. NBA.com Stats can rate-limit hosted runners. A successful data refresh does not itself prove model accuracy.

Current known data limitations:
- Some opponent and 3-point splits may be unavailable from the upstream source.
- Official injury report ingestion, verified starting lineups, player-minute rotations and player impact estimates are not yet automatically integrated into the team engine.
- Travel and injury impacts must not be guessed.
- A million simulations reduce random simulation noise; they do not repair biased inputs or a misspecified model.

## Run on GitHub
1. Open Actions and run **Update NBA Statistics**; confirm it succeeds.
2. Run **Run Doug's Elite NBA Simulator**.
3. Enter the actual home/away teams, market spread and total, rest/travel context and evidence-based injury adjustments.
4. Keep the default 1,000,000 trials; close decisions can refine to 5,000,000.
5. Download the text/JSON artifacts.

Home spread convention: enter the home team's market line, e.g. -4.5 when the home team is favored. Do not use alternate lines.

## Run locally
```bash
python -m pip install numpy
python -m unittest -v nba.test_simulator nba.test_backtest nba.test_elite_analytics
python -m nba.simulator --home BOS --away NYK --spread -3.5 --total 221.5 --trials 1000000
```

## Backtesting and calibration
Archive predictions before tipoff and pair them with actual final scores and closing lines. Then run:
```bash
python -m nba.backtest --csv nba/historical_predictions.csv
```
Review points/margin/total MAE, Brier score, log loss, calibration buckets, hit rate and closing-line value. Require chronological out-of-sample validation; never tune and evaluate on the same games. A model is not betting-ready simply because unit tests pass or the simulation completes.

## CI
The NBA Elite Simulator CI workflow runs unit tests, validates all 30 team records and runs a reproducible one-million-trial smoke matchup. CI passing validates software execution, not predictive edge.
