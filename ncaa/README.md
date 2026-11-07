# Doug's Elite NCAA Football Simulator

An independent college-football simulation module inside `dlamb9215/Douglas-Lamb`. It does not change the NFL simulator.

## Current engine

- Reproducible, seeded drive-level Monte Carlo simulation (default 100,000 trials).
- College-specific pace estimate from plays per game and expected plays per drive.
- Offense-versus-defense blend using points per game/drive, yards per play, success rate, explosive-play rate, turnover rates and team strength rating.
- Home-field adjustment, with neutral-site option.
- Moneyline, spread-cover and total over/under probabilities when sportsbook lines are supplied, including push probabilities.\n- First-half score and home-lead projections, plus team scoring 10th/50th/90th percentile ranges.
- Data-quality warnings for missing or small samples.
- JSON output containing projections, inputs, probabilities and warnings.

## Run locally

From the repository root:

```bash
python -m unittest discover -s ncaa/tests -v
python -m ncaa.cli --home Georgia --away Alabama --trials 100000 --home-spread -3.5 --total 52.5
```

## Automatic FBS data pipeline

The refresh job uses the CollegeFootballData API for FBS schedules/results, game team box scores, advanced team-season metrics, and Elo ratings. It creates:

- `ncaa/data/team_profiles.csv`: the simulator's normalized inputs
- `ncaa/data/team_rankings.json`: national comparison metrics, ranks, source and retrieval metadata

The pipeline only counts completed games and refuses to replace the dataset if the provider returns no completed games or fewer than 50 team profiles. Current-season ranks are provisional and change as games are played. Some advanced fields may be unavailable early in the season and are clearly represented by neutral fallback values in the profile.

### One-time API setup

1. Create a free CollegeFootballData account and request an API key at https://collegefootballdata.com/
2. In GitHub, open **Settings → Secrets and variables → Actions → New repository secret**.
3. Name the secret exactly `CFBD_API_KEY` and paste the API key as its value. Never put the key in a file or commit it.
4. Open **Actions → Refresh NCAA FBS Statistics → Run workflow**, select the season year and season segment, then run it.

The refresh workflow also runs on its scheduled cadence. It commits updated CSV/JSON data to the repository only after successful validation. The API key is read only from the GitHub Actions secret. CFBD access limits and endpoint entitlements depend on the provider's current plan.


Required columns:

`team,points_for,points_against,yards_per_play,yards_per_play_allowed,plays_per_game,points_per_drive,turnovers_per_game,takeaways_per_game,turnover_margin_per_game,explosive_play_rate,success_rate,strength_rating,games_sampled,source,as_of`

Optional: `points_per_drive`.

**Important:** until the CFBD API secret is configured and a successful refresh completes, the starter dataset remains an empty template. Missing teams use a league-average prior and are explicitly flagged. Do not treat prior-only output as a betting recommendation. The current collector is a first verified-data pipeline, not yet a fully calibrated betting model; backtesting and model calibration remain required.

## GitHub Actions

Open Actions → **Doug's Elite NCAA Football Simulator** → Run workflow. Enter the home and away school names, trial count, optional home spread and total, and whether the game is at a neutral site. The run uploads `ncaa-results.json` as an artifact.

## Model limitations

This engine is a transparent drive-outcome Monte Carlo model, not a play-by-play NCAA rules simulator. First-half estimates now use a separate 30-minute clock-limited drive-duration simulation with alternating possessions. It is more explicit than splitting full-game drives, but remains a drive-duration approximation, not a play-by-play clock model; it does not explicitly simulate timeouts, two-minute rules, quarter boundaries, or possession/clock strategy. It does not yet model player availability, play-calling, fourth-down decisions, overtime rules, weather, injuries, transfer portal changes, or conference-specific calibration. Its probabilities require a complete, current and consistently sourced profile file and subsequent backtesting before they should be used for wagering.

## Forecast backtesting and calibration

Save each simulator forecast before kickoff, then append the final outcomes to a CSV. Required columns are `home_win_probability,home_win`; optional paired columns are `home_cover_probability,home_cover` and `over_probability,over`. Probabilities are decimals from 0 to 1 and outcomes are 1 for yes / 0 for no.

Run:

```bash
python -m ncaa.backtest --input ncaa-predictions.csv --output ncaa-backtest-results.json
```

The report includes sample size, Brier score, log loss, accuracy, and reliability bins for each market with available data. Only forecasts recorded before kickoff should be included. This is an evaluation framework; it does not claim calibrated performance until a meaningful historical prediction ledger has been accumulated.


## Expanded team matchup layer (November 2026)

The refresh pipeline now also writes passing and rushing offense/defense splits to each team profile and the national ranking snapshot: pass yards, attempts, completions, completion rate, yards per attempt, passing TDs/interceptions/first downs, rush yards/attempts/yards per carry/TDs/first downs, opponent pass/rush yards and attempts, and yards allowed per completion/attempt/carry where the source fields are present. National ranks are generated for passing/rushing efficiency and passing/rushing defense. Each simulation JSON includes a side-by-side offense/defense/turnover profile and the national rank context for the two teams. Pass and rush efficiency matchup terms now contribute to expected points per drive when valid source metrics exist.

These added fields depend on the next successful CFBD refresh; existing CSV files will continue to load with default zero values for newly added fields until refreshed. A zero or missing metric is not evidence of poor performance; it means the provider did not supply the field.

Still not automated in this release: verified injury/availability reports, confirmed starting quarterbacks and depth charts, player-level usage/props, venue-specific weather, live line ingestion and vig removal, scenario-based injury/game-script runs, and an independent first-half clock model. Do not treat the current output as fully calibrated or as a guaranteed betting edge.

## Sportsbook price comparison

Optional CLI inputs accept American moneyline and totals prices. When both sides are supplied, the CLI removes proportional two-way vig, compares the model probability with the fair market probability, and reports expected value per $100 at the quoted price. Example:

```bash
python -m ncaa.cli --home Georgia --away Alabama --trials 500000 --home-spread -3.5 --total 52.5 --home-ml-odds -165 --away-ml-odds 145 --over-odds -110 --under-odds -110
```

This is price math only: it does not fetch live sportsbook prices, guarantee a positive edge, or account for limits, stale lines, correlated parlays, or market movement. Use exact book prices and record their timestamp.

## Readiness and data gates

The team-level simulator can run from a validated CFBD refresh and accepts user-entered market lines. It deliberately does not invent injury status, confirmed starting quarterbacks, player snap/route/touch projections, or weather. CFBD documents that weather availability varies and its weather endpoint requires an eligible paid tier. No verified injury feed is currently wired into this repository. Treat these as manual pregame checks until a trustworthy source is configured. Forecasts remain uncalibrated until a sufficiently large, timestamped pregame ledger is collected and evaluated with `ncaa.backtest`.


## Scenario stress testing (added November 2026)

Every CLI matchup now includes six separately seeded sensitivity runs in the JSON output and terminal summary: baseline, home offense reduced 10%, away offense reduced 10%, both offenses reduced 10%, both teams' pace reduced 8%, and both teams' pace increased 8%. These are transparent assumption stress tests. They are **not** injury-status reports, not weighted scenarios, and not calibrated probabilities. The base forecast remains the primary projection. Scenario results are intended to show whether a pick is fragile to reasonable changes in efficiency or pace.

Verified injuries, confirmed starting quarterbacks, depth charts and player usage remain pregame manual checks because no trustworthy automated feed is configured. Entering an assumption into a scenario is not evidence that a player is injured or unavailable.

## Sourced pregame verification gate

The CLI accepts `--pregame-checks checks.json` and an optional `--require-verified-pregame` flag. The latter blocks the matchup unless all six checks are marked verified with a nonempty source and an offset-aware timestamp no older than 24 hours. Checks are: home and away starting QB, home and away injury report, weather, and sportsbook prices. Team names must match. Without a file, the output explicitly says that pregame checks are unverified. This is a manual provenance gate, **not** an automatic source lookup or independent authentication.

Example `checks.json` structure (fill in real sourced details, not placeholders):

```json
{
  "home_team": "Georgia",
  "away_team": "Alabama",
  "checks": {
    "home_starting_qb": {"verified": false},
    "away_starting_qb": {"verified": false},
    "home_injuries": {"verified": false},
    "away_injuries": {"verified": false},
    "weather": {"verified": false},
    "sportsbook": {"verified": false}
  }
}
```

For each genuinely verified entry, add `"source": "source name or URL"`, `"checked_at": "2026-11-07T12:00:00Z"`, and the relevant observations. A verified check means only that the provided metadata passed format and freshness validation; it does not certify that a source is accurate. Do not claim a matchup is fully vetted without independent confirmation.


## Player workload and prop simulations

Optional `--players player-inputs.json` adds player-level Monte Carlo outputs and probabilities for user-supplied prop lines. Each player entry requires player/team/role, expected opportunities, success probability, yards per success, yards standard deviation, touchdown rate per opportunity, source and an ISO date. Inputs older than two days are rejected. For a receiver, opportunities can represent targets and success probability the catch rate; for a rusher, opportunities can represent carries and success probability should normally be 1.0; for a QB, opportunities can represent pass attempts and success probability completion rate. The generic output is an opportunity/success/yards model and is not a complete position-specific stat model: it does not yet separate passing, rushing and receiving yards for dual-role players, model sacks/interceptions, or correlate players on the same team.

Example structure (replace all values with real, sourced pregame data):

```json
[
  {
    "player": "PLAYER NAME",
    "team": "TEAM NAME",
    "role": "RB",
    "expected_opportunities": 18.0,
    "success_probability": 1.0,
    "yards_per_success": 4.5,
    "yards_sd_per_success": 2.0,
    "touchdown_rate_per_opportunity": 0.03,
    "source": "source name or URL",
    "as_of": "2026-11-07",
    "prop_lines": {"yards": 70.5, "opportunities": 17.5, "touchdowns": 0.5}
  }
]
```

The GitHub workflow accepts optional `player_inputs` JSON, sourced `pregame_checks` JSON, and moneyline/total American odds. It writes these as temporary run inputs and includes the results in the uploaded artifact. Do not enter guessed workloads or mark availability verified without checking a current source.


## Automated CFBD player-data cache

The scheduled/dispatch team refresh now has a separate optional player-data refresh step. It requests season player statistics from `/stats/player/season` and player usage metrics from `/player/usage`, and saves the raw sourced response with retrieval metadata to `ncaa/data/player_season_data.json`. The separate status file records endpoint availability and provider warnings. If player stats are unavailable or the account lacks entitlement, the workflow preserves the previous player cache and continues the team simulation; it does not silently convert missing player data into zeroes. This is season production/usage context, not real-time availability, confirmed starter status, or a complete player projection feed. The CFBD API account must have access to the relevant endpoints.


## First-half projection method update

The first-half projection runs a separate 30-minute simulation. Each possession consumes a sampled drive duration and possession alternates between teams. The output includes expected first-half drives by team. This is a clock-limited drive-level approximation, not a full play-by-play engine; end-of-half clock management, timeouts, quarter boundaries and two-minute strategy are not explicitly represented.


When CFBD player stats refresh succeeds, the matchup workflow attempts to build player inputs automatically for the two selected teams. It uses player games played when the provider includes it; otherwise it uses the team's completed-game count and labels that fallback in the output. QB workload is based on season pass attempts/completions; RB on carries; WR/TE on receptions. This is a season-average workload baseline, not a depth-chart-adjusted projection. The per-opportunity yardage standard deviation is a documented heuristic (60% of average yards, with a 2-yard floor), not a fitted player-specific variance. The generated output retains player sample size and denominator provenance.
