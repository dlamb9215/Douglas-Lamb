# Doug's Elite Game Simulator

Team-level NFL matchup simulator. Player-prop projections are not part of the active game simulator.

## What it produces

- Two-team passing, rushing, and total offense-versus-defense comparison
- Team yardage and scoring projections
- Turnover comparison
- Full-game and first-half moneyline, spread, and total probabilities
- Vig-free sportsbook comparison when odds and lines are supplied
- Reproducible Monte Carlo runs (default: 100,000 trials)

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
- Current team-stat inputs are through the most recently completed refresh; verify the data timestamp and injury/news reports before betting.
- The scoring model uses team scoring averages and opponent points allowed, with drive-level Monte Carlo variation. It is a model estimate, not a guarantee or a historically proven edge.
- First-half probabilities are approximate splits of full-game scoring.
- The simulator does not currently verify official inactives, starting quarterbacks, weather, or sportsbook line movement automatically. Check those before final picks.
