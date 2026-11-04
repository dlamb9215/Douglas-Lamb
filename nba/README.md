# Doug's Elite NBA Simulator

A separate NBA engine in the existing dlamb9215/Douglas-Lamb repository. It does not change or import the NFL engine.

## Model
- Pace × offensive/defensive efficiency projections.
- Team-vs-team offense and defense comparison.
- NBA Four Factors: eFG%, turnover rate, offensive rebounding rate and free-throw rate, including opponent-side factors.
- Full-game and first-half Monte Carlo probabilities.
- Moneyline, spread and over/under; optional vig-free market comparison.
- 1,000,000 default trials; borderline matchups automatically refine to 5,000,000.
- Fixed seeds for reproducibility.
- Current season blended with prior season using an eight-game prior weight to reduce early-season noise.

## Refresh data
Run the Update NBA Statistics workflow. It fetches Advanced and Four Factors dashboards from NBA.com Stats for the current and prior seasons. It validates all 30 teams and only replaces the data file after a complete successful refresh. Rate limits may cause a run to fail; the last good data file is preserved.

## Run locally
    python -m pip install numpy
    python -m unittest -v nba.test_simulator
    python -m nba.simulator --home BOS --away NYK --spread -3.5 --total 221.5 --trials 1000000

## GitHub Actions
Open Actions, select Run Doug's Elite NBA Simulator, enter home and away abbreviations, optional spread and total, and trials. Download the nba-matchup-results artifact. Refresh NBA statistics first if the data file is missing or stale.

## Limitations
This first release is a team-level model. It does not yet project player minutes, rotations, player props, confirmed starting lineups or injuries. Enter sportsbook lines manually. No alternate spreads are generated. Probabilities are estimates, not guarantees or proof of a profitable edge.
