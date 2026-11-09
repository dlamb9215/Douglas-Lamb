# Doug's Elite NBA Simulator

A team-level NBA forecasting and betting-analysis engine. It is separate from the NFL simulator.

## Included model features
- Matchup pace estimate and offensive rating versus opposing defensive rating.
- NBA Four Factors: effective field-goal percentage, turnover rate, offensive rebounding rate and free-throw rate, plus opponent-side factors.
- Full-season statistics blended with the prior season using an eight-game prior weight.
- Recent-form features are supported by the engine but currently unavailable from the connected data provider, so they are not applied.
- Home/road splits are supported by the engine but currently unavailable from the connected data provider; overall ratings are used instead.
- Team scoring variance currently uses a fixed fallback because the connected team-stat provider does not supply team game-log residuals.
- Schedule adjustments for rest, back-to-backs and travel distance. When `--game-date` is supplied, the simulator checks ESPN's public scoreboard for the matchup, derives each team's days of rest from the prior 10 calendar days, and removes home-court advantage for a neutral-site event. Travel distance remains unset unless verified itinerary/venue coordinates are available.
- Optional official NBA injury-report PDF ingestion by game date, including player status rows and team-submission warnings. It reports Out/Questionable/Doubtful/Probable/Available designations but does not invent player-minute or team-point impacts; those still require player-level modeling.
- Correlated full-game and first-half Monte Carlo score distributions. Regulation ties are resolved with stochastic five-minute overtime periods so NBA moneyline probabilities do not split regulation ties as half-wins.
- Full-game moneyline confidence intervals plus first-half moneyline win/tie probabilities.
- Spread and total probabilities, pushes, projected score, projected margin, projected total, and model-vs-line edge.
- 1,000,000 baseline trials; borderline matchups refine to 5,000,000 trials.
- Fixed seeds and machine-readable JSON output for auditability.
- Betting leans require both at least 55% model probability and at least 1.5 points of model line edge. Otherwise the output is PASS.
- Historical evaluation utility reports point MAE, margin/total MAE, Brier score, log loss, calibration buckets, hit rates and optional closing-line movement.
- Optional The Odds API v4 integration retrieves current NBA moneyline, spread and total markets across US books, selects best prices at the selected consensus line, reports no-vig market probabilities and calculates expected net value per $100 risked. Manual odds remain supported. Spread/total EV accounts for pushes as stake refunds; moneyline ties are split evenly between teams in the model estimate.
- A shared data-quality gate validates all 30 expected teams, metric ranges, season metadata, timezone-aware timestamps and 72-hour freshness; it reports early-season sample-size and unavailable-feature warnings without inventing values.

## Output scope
The team engine provides moneyline probabilities plus spread and game-total analysis for full game and first half. No alternate spreads are created. The experimental `nba.player_props` pipeline builds player points/rebounds/assists/PRA projections from ESPN feeds, but only after a fresh confirmed-lineup/minutes input is supplied. Player props are separate from the team score model and are not yet calibrated betting recommendations.

## Refresh data
Run the **Update NBA Statistics** workflow. It requests current and prior-season ESPN-derived team aggregates through DunkAPI. The updater validates all 30 teams and writes only after both season requests and data checks succeed. It preserves the last good file if a refresh fails.

To fetch the official injury report, supply `game_date` and enable `auto_injuries`; this downloads the latest NBA league injury-report PDF for that date and fails closed if only stale reports are available. To enable live sportsbook lines, add an `ODDS_API_KEY` Actions secret and select `auto_odds` when launching the matchup workflow. The integration uses The Odds API v4 featured NBA markets; coverage and quota depend on the account plan. Without the secret, leave `auto_odds` disabled and enter actual sportsbook lines/prices manually. The scheduled updater uses the 2026-27 season and 2025-26 as the prior baseline. Confirm the season settings when a new season begins. It requires the `DUNKAPI_API_KEY` Actions secret. The team-stat provider does not currently supply all opponent Four Factors, recent form, home/road splits, rotations, 3P accuracy, or team game-log residual distributions; the model uses documented neutral/fixed fallbacks rather than fabricating these fields. The matchup workflow rejects data older than 72 hours. ESPN's public scoreboard adapter supplies schedule event identity, neutral-site status and recent rest context, but it is an undocumented feed and does not replace official NBA injury reports or a supported data contract.

## Run on GitHub
1. Open Actions.
2. Run **Update NBA Statistics** and confirm it completes successfully.
3. Run **Run Doug's Elite NBA Simulator**.
4. Enter home/away abbreviations and manual team-level injury point adjustments. The optional `player_props` stage fetches rosters, game logs and the official injury report, but **withholds every player prop unless you also supply a fresh `confirmed_lineups_json` input** with confirmed players, availability and projected minutes/uncertainty. This prevents roster membership from being mistaken for a confirmed game lineup. For manual player-prop lines, provide a JSON mapping of player names to stat lines using `--lines-json`. Either select `auto_odds` (after adding `ODDS_API_KEY`) or enter actual sportsbook lines and prices manually. Supply the game date for ESPN schedule/rest/neutral-site context; enable `auto_injuries` to fetch the NBA's official injury report.
5. Keep the default 1,000,000 trials. The engine increases borderline runs to 5,000,000.
6. Download the text and JSON results artifact.

Spread convention: enter the home team's sportsbook line (for example, -4.5 when the home team is favored). Enter only the actual market line; no alternate line recommendations are generated.

## Run locally
```bash
python -m pip install numpy
python -m unittest -v nba.test_simulator nba.test_backtest nba.test_data_quality nba.test_schedule nba.test_odds nba.test_injuries nba.test_player_props nba.test_player_props_backtest
python -m nba.simulator --home BOS --away NYK --spread -3.5 --total 221.5 --trials 1000000
```

## Automated code checks
The `NBA Simulator CI` workflow runs unit tests, backtest tests, 30-team data validation, and a command-line smoke test on relevant code changes. Passing CI validates software behavior, not predictive accuracy.

## Confirmed player props and validation

The experimental player-prop workflow requires a fresh, timezone-aware lineup JSON input. The top-level object must include `source`, `confirmed_at` and `teams`. The timestamp must be no more than 12 hours old. Team keys must match the provider codes (for example, `BOS`, `NY`, `GS`, `NO`; `NYK` is normalized to `NY`).

Example:
```json
{
  "source": "Official team lineup report",
  "confirmed_at": "2026-11-09T18:30:00-05:00",
  "teams": {
    "BOS": {
      "Player Name": {
        "confirmed": true,
        "status": "available",
        "minutes": 34,
        "minutes_sd": 2.5
      }
    },
    "NY": {
      "Another Player": {
        "confirmed": true,
        "status": "probable",
        "minutes": 32,
        "minutes_sd": 3
      }
    }
  }
}
```

Each projected player must be explicitly confirmed, available/probable, and have a bounded game-specific minutes estimate. Players absent from the supplied lineup, questionable/doubtful/out, or with uncertain minutes are withheld. The official NBA injury report is also checked. If the lineup input is missing, stale, incomplete or untrusted, the player-prop artifact reports that props were withheld instead of generating picks. The player-prop model remains experimental: usage changes, matchup-position defense and teammate-absence impact are not automatically modeled.

Archive player-prop rows with `player,stat,projection,actual,line,over_probability` in a CSV and run:
```bash
python -m nba.player_props_backtest --csv nba/player_prop_history.csv
```
This reports projection MAE, Brier score, log loss, hit rate and probability calibration by points/rebounds/assists/PRA. Pushes are excluded from binary over/under scoring; keep all non-push wins and losses. Never tune and evaluate on the same games.

## Historical validation
Build a CSV of archived pregame predictions and final scores with the columns described in `nba/backtest.py`. Run:
```bash
python -m nba.backtest --csv nba/historical_predictions.csv
```
Do not call the model calibrated until it has enough chronologically separated out-of-sample games and its calibration, Brier score, log loss, MAE and closing-line value have been reviewed. The backtest script evaluates data supplied to it; it does not fabricate historical predictions or results.

## Known limitations
- Team-level injury point adjustments are manual. No official inactive/lineup feed is currently integrated.
- Rest days and neutral-site status can be fetched from ESPN's public scoreboard when a game date is supplied. Travel miles are not auto-computed. ESPN's feed is undocumented and may change; schedule lookup failure blocks the requested auto-context run.
- Official NBA injury designations are ingested, but the system does not automatically verify starting lineups or player rotations. Player props require a fresh, user-supplied confirmed lineup and game-specific minutes file; missing, stale or uncertain entries are withheld. Player-level impact estimates and a calibrated player-prop probability model are not implemented. The separate manual player-prop simulator also requires verified user-supplied inputs. Automatic travel-mile calculation and play-by-play possession simulation are also not implemented. Live featured odds require the user to add an Odds API key and enable the workflow input.
- The score distribution is a transparent approximation pending fitting against historical game residuals. One million trials reduce Monte Carlo sampling noise; they do not correct bad inputs or model misspecification.
- Probabilities are estimates, not guaranteed outcomes or proof of a profitable betting edge.

 
## Data-readiness gate

`python -m nba.data_quality --data nba/team_stats.json --max-age-hours 72` is run by the CI, statistics-refresh and matchup workflows. It blocks incomplete, malformed, future-dated or stale team data and reports warnings for small current-season samples and provider fields that are unavailable. Passing this gate means the input file is structurally ready; it does not establish predictive calibration or a profitable betting edge.
