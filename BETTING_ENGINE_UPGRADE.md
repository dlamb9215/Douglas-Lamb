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
- NFL team markets require a fresh `game_day_confirmations.json` with `all_inactives_reviewed: true`, an HTTPS `source_url`, and at least 22 confirmed active starters for each team.
- NBA player props flow through the shared engine only after the existing official injury and confirmed minutes/lineup gates pass.
- Each market report includes no-vig probability, breakeven probability, expected value, edge, quote age, and explicit blockers.

## NBA workflow launch configuration

GitHub allows at most 10 `workflow_dispatch` inputs. The NBA launch form now
uses eight fields: home, away, spread, total, trials, max trials, game date,
and `game_config_json`. Optional market and context values go in that final
JSON object. Supported keys include:

- `home_ml_odds`, `away_ml_odds`, `home_spread_odds`, `away_spread_odds`,
  `over_odds`, `under_odds` (or shared `spread_odds` / `total_odds`).
- `odds_source`, `odds_checked_at` for manually supplied prices.
- `confirmed_lineups_json`, `player_prop_lines_json`.
- `player_props`, `prop_trials`, `auto_injuries`, `espn_bet_odds`,
  `auto_odds`, `home_rest`, `away_rest`, `home_travel`, `away_travel`,
  `home_injury_points`, `away_injury_points`, and `seed`.

Example minimal market config:

```json
{
  "home_ml_odds": -145,
  "away_ml_odds": 125,
  "home_spread_odds": -110,
  "away_spread_odds": -110,
  "over_odds": -108,
  "under_odds": -112,
  "odds_source": "Example Sportsbook",
  "odds_checked_at": "2026-11-12T18:30:00Z",
  "auto_injuries": true,
  "espn_bet_odds": false,
  "auto_odds": false
}
```

Do not set both `espn_bet_odds` and `auto_odds` to true. For automatically
fetched prices, leave manual prices/source/timestamp out of the config.

## NBA player-prop quote format

For `player_prop_lines_json`, each priced player/stat entry should include
`line`, `over_odds`, `under_odds`, a sportsbook `book` or `source`, and a
timezone-aware `quoted_at` (or `checked_at_utc`) timestamp. Example:

```json
{
  "Example Player": {
    "points": {
      "line": 24.5,
      "over_odds": -115,
      "under_odds": -105,
      "book": "Example Sportsbook",
      "quoted_at": "2026-11-12T18:30:00Z"
    }
  }
}
```

The NBA lineup JSON must contain each team under `teams`, with at least five
entries per team explicitly marked `confirmed: true`, `status: available` or
`probable`, `starter: true`, plus bounded `minutes` and `minutes_sd`.
The timestamp and source are required. The team-market gate additionally
requires the official NBA injury report to show both teams submitted.

## Current limitations and release gates
The integration is end-to-end at the report/decision layer, but it is **not yet certified to issue BET recommendations**. Calibration remains deliberately false for NBA team markets, NBA player props, NFL team markets, and NFL player props until market-specific, time-ordered out-of-sample ledgers meet the review standard. NFL team markets remain blocked until the team-level confirmation file explicitly attests that the full inactive list was reviewed and includes 22 active starters for each team. Do not manually set calibration flags true or treat green CI as proof of predictive accuracy.

Automatic sportsbook coverage depends on configured providers/API keys. The NBA Odds API and ESPN BET adapters may return no prices for an event; missing prices remain PASS. NFL market prices are entered as a timestamped two-sided snapshot. Never infer a market price from the usual -110 convention.

Do not describe any output as profitable or validated until the historical ledger has enough settled, chronologically separated observations and calibration/ROI/closing-line-value reviews are satisfactory.


## Multi-source NBA data preflight

Every manual NBA simulation now runs `python -m nba.data_hub` before the
Monte Carlo engine and uploads `nba-data-readiness.json` and
`nba-data-readiness.txt` with the game artifacts. The report records provider,
retrieval/update timestamps, source URLs where available, warnings, and
separate readiness flags. A missing source does not get replaced by invented
values; it is reported as unavailable and the existing betting gates remain
fail-closed.

Current integrations:
- **Team efficiency and Four Factors:** the repository's validated,
  timestamped `nba/team_stats.json` feed (currently ESPN-derived through the
  existing DunkAPI data refresh). The preflight checks all 30 teams, required
  metrics, numeric ranges, sample size, provenance, and freshness.
- **Schedule/rest context:** ESPN public NBA scoreboard adapter. This is a
  public, undocumented feed; schedule/rest is contextual and does not prove
  availability or travel miles.
- **Injuries:** NBA official injury-report PDF parser first; the existing ESPN
  injury feed is labeled third-party fallback only. Fallback data never counts
  as official availability confirmation.
- **Market odds:** The Odds API v4 when `ODDS_API_KEY` is configured, plus the
  existing ESPN BET adapter. Actual source and quote update times are retained;
  absent prices remain missing.
- **Starting lineups and minutes:** supplied game-specific
  `confirmed_lineups_json` only. Roster/depth-chart or projected lineup
  information is not silently promoted to a confirmed starting five.

### Optional API setup

In GitHub, open Settings -> Secrets and variables -> Actions and add
`ODDS_API_KEY` using a key from The Odds API. The simulator already reads this
secret. Do not put API keys in workflow JSON, source files, or commits.

Sportradar offers a paid/licensed NBA API with official statistics, injuries,
depth charts and substitution data; it is not required for this pipeline and
has not been wired as a live source because it requires a separately provisioned
account/key and entitlement. A depth chart is not a confirmed game lineup.
RotoWire lineup pages can be used for human cross-checking, but are not treated
as a structured official source by the automated gate.

The readiness report is a preflight, not a calibration report. Even when every
data source is present, the market-specific out-of-sample calibration gate
must independently pass before a candidate can become BET.


## Versioned NBA forecast ledger and settlement

Every successful manual NBA matchup run appends a pregame forecast to
`nba/ledger/predictions.csv` using the workflow run ID, source data timestamp,
event ID, scheduled tip time, trial count, model probabilities, market lines,
and per-market bookmaker/quote timestamps. The ledger writer is idempotent and
refuses schema mismatches rather than overwriting history.

The scheduled workflow `.github/workflows/settle-nba-ledger.yml` checks the
ESPN public scoreboard daily. It settles a row only when the exact archived
event ID is found, both team identities match, the event is marked completed,
and both final scores are present. Unfinished games remain pending; mismatched
events are reported and never settled.

Run a backtest with:

```bash
python -m nba.backtest --csv nba/ledger/predictions.csv
```

The evaluator excludes unsettled rows and forecasts timestamped at/after
scheduled tip, rejects duplicate forecast IDs, and reports sample counts,
Brier score, log loss, calibration bins, point errors, and available closing
line movement. A minimum of 200 settled predictions per market is reported as
a sample-size checkpoint only. It does not automatically open the betting
calibration gate. Chronological holdout performance, market-baseline
comparisons, positive closing-line value, and manual review remain required.
