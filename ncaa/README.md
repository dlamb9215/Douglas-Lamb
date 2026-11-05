# Doug's Elite NCAA Football Simulator

An independent college-football simulation module inside `dlamb9215/Douglas-Lamb`. It does not change the NFL simulator.

## Current engine

- Reproducible, seeded drive-level Monte Carlo simulation (default 100,000 trials).
- College-specific pace estimate from plays per game and expected plays per drive.
- Offense-versus-defense blend using points per game/drive, yards per play, success rate, explosive-play rate, turnover rates and team strength rating.
- Home-field adjustment, with neutral-site option.
- Moneyline, spread-cover and total over/under probabilities when sportsbook lines are supplied.
- Data-quality warnings for missing or small samples.
- JSON output containing projections, inputs, probabilities and warnings.

## Run locally

From the repository root:

```bash
python -m unittest discover -s ncaa/tests -v
python -m ncaa.cli --home Georgia --away Alabama --trials 100000 --home-spread -3.5 --total 52.5
```

## Team data

Populate `ncaa/data/team_profiles.csv` with verified current-season team data. One row per school. Rates are decimals (for example, 0.45 = 45%). `strength_rating` is a relative rating on a consistent scale; use the same scale for every team. `points_per_drive` is optional; if blank it is estimated from points per game and expected drives.

Required columns:

`team,points_for,points_against,yards_per_play,yards_per_play_allowed,plays_per_game,turnovers_per_game,takeaways_per_game,explosive_play_rate,success_rate,strength_rating,games_sampled,source,as_of`

Optional: `points_per_drive`.

**Important:** the starter dataset is intentionally empty. If a team is missing, the engine uses a league-average prior and clearly flags it. Do not treat prior-only output as a betting recommendation. A reliable live data ingestion pipeline and calibration against historical NCAA results are the next upgrade phase; no current-season stats are fabricated or silently assumed.

## GitHub Actions

Open Actions → **Doug's Elite NCAA Football Simulator** → Run workflow. Enter the home and away school names, trial count, optional home spread and total, and whether the game is at a neutral site. The run uploads `ncaa-results.json` as an artifact.

## Model limitations

This first engine is a transparent drive-outcome Monte Carlo model, not a play-by-play NCAA rules simulator. It does not yet model player availability, play-calling, fourth-down decisions, overtime rules, weather, injuries, transfer portal changes, or conference-specific calibration. Its probabilities require a complete, current and consistently sourced profile file and subsequent backtesting before they should be used for wagering.
