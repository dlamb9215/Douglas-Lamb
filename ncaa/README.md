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

This engine is a transparent drive-outcome Monte Carlo model, not a play-by-play NCAA rules simulator. First-half estimates split simulated drives approximately in half; they are not a separate clock-accurate half-game engine. It does not yet model player availability, play-calling, fourth-down decisions, overtime rules, weather, injuries, transfer portal changes, or conference-specific calibration. Its probabilities require a complete, current and consistently sourced profile file and subsequent backtesting before they should be used for wagering.
