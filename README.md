# Doug's Elite Game Simulator

Team-level NFL matchup simulator. Player-prop projections are not part of the active game simulator.

## What it produces

- Two-team passing, rushing, and total offense-versus-defense comparison
- Team yardage and matchup-adjusted scoring projections
- Data season, refresh timestamp, and 32-team validation
- Turnover comparison
- Full-game and first-half moneyline, spread, and total probabilities
- Vig-free sportsbook comparison when odds and lines are supplied
- Reproducible Monte Carlo runs (default: 100,000 trials)
- 95% Wilson confidence intervals for simulated event probabilities, showing Monte Carlo sampling uncertainty

## Run one matchup

```bash
python -m unittest -v
python main.py --home BUF --away BAL --trials 100000
```

Team abbreviations must be standard NFL abbreviations. The home team is `--home`; the away team is `--away`.

Optional market inputs:

```bash
python main.py --home BUF --away BAL --spread -3.5 --total 47.5 --home-odds -150 --away-odds 130 --over-odds -110 --under-odds -110 --trials 100000
```

## Run from GitHub

1. Open **Actions** in this repository.
2. Select **Run Doug's Elite Game Simulator**.
3. Select **Run workflow**.
4. Enter the home team, away team, and trial count (use 100000).
5. Open the completed run and download `matchup-simulation-results`.

The workflow runs tests before the simulation and saves the text report as an artifact.

## Data and limitations

- Team statistics are refreshed by the scheduled **Update NFL Statistics** workflow (Tuesday 12:00 UTC) and can also be run manually from Actions.
- The simulator blocks a matchup when required team statistics are missing.
- The current checked-in `nfl_team_stats.json` has 32-team coverage and 7–8 games per team, but its records currently omit `season` and `data_updated_at`. The simulator now prints a freshness warning instead of implying that this file has a verified refresh time. The stats updater must populate those metadata fields before freshness can be certified. Validation rejects invalid team coverage, games played, and scoring averages. Treat this early-season sample cautiously.
- Scoring projections blend team points scored with opponent points allowed, then apply a shrunk offense-versus-defense yardage adjustment and a 1.5-point home-field assumption. This adjustment is transparent but not yet empirically calibrated.
- Rankings are calculated for each available passing, rushing, total-offense, total-defense, and turnover metric. Higher is better for offensive production and takeaways; lower is better for defensive allowances and giveaways.
- The scoring model uses team scoring averages and opponent points allowed, with drive-level Monte Carlo variation. Turnover probabilities are applied to drives, while non-turnover drive scoring is normalized so the observed team scoring averages are not reduced a second time by the same historical turnovers.
- The weekly statistics workflow archives immutable timestamped copies in `data_snapshots/`. These snapshots establish an auditable pregame data history for future out-of-sample backtesting; they do not retroactively create missing historical snapshots.
- Tied regulation outcomes receive a simplified overtime approximation with one possession per team; a tie can remain. This is not a full NFL rules/play-by-play overtime engine.
- The model is an estimate, not a guarantee or a historically proven edge.
- First-half probabilities are approximate splits of full-game scoring.
- The player pool is sourced from nflverse and the pregame gate checks feed age, depth-chart QB1 status, and injury designations. Depth-chart order is not official game-day confirmation; official inactives and starters remain unverified until supplied by authoritative game-day sources. Weather is context only and does not apply an unvalidated scoring adjustment. Sportsbook lines are manually supplied and timestamp-checked; automatic odds and line movement are not integrated.


## NFL pregame workflow

Run a matchup manually from **Actions → Run Doug's Elite Game Simulator → Run workflow**.
Choose the home and away abbreviations; the default trial count is 100,000. Optional sportsbook inputs are spread, total, home/away American moneyline odds, and over/under American odds.

Each manual run refreshes current-season team statistics and the latest nflverse player, roster, depth-chart, and weekly injury feeds. The pregame check validates data age, reads the current depth-chart QB1, and blocks team probabilities if either team has no active QB1 in the feed. A depth-chart listing is not proof of the official game-day starter.

The workflow intentionally does **not** create player props. Final game-day inactives and official starting lineups must be confirmed separately. Team-score injury adjustments, stadium weather adjustments, automatic sportsbook odds, and historical probability calibration are not yet integrated. The output labels these limitations and is not a betting-ready recommendation.

Code pushes run validation only; matchup simulations require an explicit manual workflow dispatch.


## Validation status and safeguards

- Monte Carlo event probabilities now include two-sided 95% Wilson intervals. These quantify simulation sampling error only; they do not measure model misspecification or guarantee predictive accuracy.
- The player-feed normalizer maps nflverse's legacy `LA` code to the simulator's canonical `LAR` code for Rams player and injury lookups.
- A run must not be described as betting-ready solely because the simulation completed. Current official starters/inactives, verified team-stat freshness, current sportsbook prices, weather treatment, and out-of-sample calibration are separate readiness gates.
- Do not issue player props from this team-level simulator. Its active output is team-level only.
