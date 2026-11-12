# NFL Simulator: Game-Day Inputs and Readiness

## Current validation status

The technical CI workflow verifies imports, unit tests, fresh pregame-context generation, and a reproducible 100,000-trial smoke simulation. A successful smoke run is **not** a betting-readiness approval.

The NFL validation workflow now attempts to fetch matchup-specific kickoff weather automatically (weather failure is non-blocking), and exposes optional spread, total, two-way moneyline, and over/under price inputs. If any market field is supplied, the workflow requires a sportsbook/source name and a timezone-aware ISO-8601 timestamp no older than six hours.

NFL team statistics refresh daily at 12:00 UTC. Player data refreshes daily at 13:30 UTC.

## Run the NFL workflow

Open **Actions → Run Doug's Elite Game Simulator → Run workflow**.

- Choose the home and away team abbreviations.
- Keep trials at 100,000 for the baseline.
- Enter market lines only when they have been checked recently.
- The spread is the **home-team handicap** (home -3.5 means the home team is laying 3.5).
- If any spread, total, or odds are supplied, also supply the sportsbook source and an ISO-8601 timestamp with timezone. Market snapshots older than six hours are rejected.

## Neutral-site handling

The scoring engine removes its home-field adjustment when the weather/schedule context identifies a neutral-site venue. The manual `neutral_site` input is an additional override for cases where the schedule/weather feed cannot identify the venue. It defaults to false for ordinary home games.

## Final player availability

The nflverse roster, injury and depth-chart feeds are useful pregame context, but are not official final inactive lists. The player-prop workflow therefore requires a separate `game_day_confirmations.json` file.

Copy `game_day_confirmations.example.json` to `game_day_confirmations.json` and replace the example player with every player being considered. Set `status` to `active`, `inactive`, or `out`; set `starter` to true only for a confirmed starter. Use an official NFL/team game-day source and refresh `checked_at_utc`. The confirmation file expires after 24 hours. Missing, inactive, doubtful/questionable-from-feed-only, or non-starter players are blocked.

If the file is absent, the workflow creates an empty placeholder so the game simulation can still complete, but all player props remain blocked.

## Shared NFL BET/PASS engine and team-market confirmation

NFL game markets now pass through the shared `betting_engine` adapter. It requires both prices for a two-way market, a sportsbook/source, and a timezone-aware quote timestamp no older than six hours. Spread markets require separate home-side and away-side American prices; the workflow inputs are **Home spread odds** and **Away spread odds**. Do not enter an assumed -110 price.

To allow the team-market availability gate to pass, `game_day_confirmations.json` must contain:
- `all_inactives_reviewed: true` after the complete official inactive list has been reviewed.
- An HTTPS `source_url` for the official league/team game-day report.
- At least 22 players per team with `status: active` and `starter: true`.
- A fresh `checked_at_utc` timestamp and source description.

The workflow creates an empty blocked placeholder if this file is absent. That allows the simulation to run but cannot unlock a BET recommendation. NFL team-market calibration remains blocked until the historical ledger is reviewed out of sample.


Copy `player_prop_lines.example.json` to `player_prop_lines.json`. Replace the example data with current lines and prices. The quote timestamp must be within six hours. The key format is `TEAM:Player Name:stat`, for example `BUF:Example Receiver:receiving_yards`.

Both over and under prices are required to remove vig. The report calculates model edge and expected value per $100, accounting for push probability. Without both prices, it reports the simulated distribution without a vig-free edge.

## Model additions

- Recent five-week player game logs include per-game standard deviations.
- Player yards receive a conservative, capped opponent-defense adjustment.
- QB passing yards blend the recent baseline with completions per game × opponent passing yards per completion.
- Recent snaps, snap share, targets and carries are included as workload context. Routes and red-zone opportunity counts are explicitly marked unavailable when absent from the source feed.
- Injury exposure is summarized using reported designations and snap share. It is a relative sensitivity index, **not** a points deduction.
- Kickoff weather is matched to the NFL schedule and venue and fetched from Open-Meteo. Weather is context only until coefficients are validated out of sample.
- Forecasts are written to `nfl_forecast_ledger.csv`; later workflow runs reconcile completed scores and report Brier scores for moneyline, spread and totals.

## What is still required before real betting recommendations

The software deliberately does not claim full betting readiness. Do not override these gates manually or infer betting readiness from a green GitHub Actions run. Final official inactives and starters must be supplied for each game, market lines must be sourced and timestamped, and the forecast ledger needs a meaningful time-ordered sample (at least 100 settled games for an initial review, preferably multiple seasons). Weather and injury coefficients, prop dispersion, expected value, ROI and closing-line value still require out-of-sample validation. The current workflow labels outputs as model indications, not betting picks, until these gates are met.

A 100,000-trial simulation reduces Monte Carlo noise; it does not make an uncalibrated projection accurate.
