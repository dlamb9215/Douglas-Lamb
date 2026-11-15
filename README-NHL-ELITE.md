# Doug's Elite NHL Simulator

## Launch

1. Open the repository's **Actions** tab.
2. Select **Run Doug's Elite NHL Simulator** (`run_nhl_elite.yml").
3. Select the home and away NHL team abbreviations.
4. Leave trials at 100,000 for the default run, or choose 250,000, 500,000, 1,000,000, or 5,000,000.
5. Enter the current sportsbook game total and optional American odds. Enter 0 for odds you do not have.
6. If confirmed starting goalies are known, enter their NHL player IDs. Otherwise the model selects the goalie with the strongest season-start sample and labels it as projected, not confirmed.
7. Launch the workflow. Download the `dougs-elite-nhl-results" artifact after it completes.

## Model inputs

The workflow fetches current-season team, skater, goalie, and roster information from the public NHL Stats REST and NHL Web APIs. It fails closed when essential team scoring data is missing rather than silently inserting league averages.

## Markets and projections

- Full-game moneyline with regulation-tie rate and an overtime/shootout winner proxy.
- Puck line +/-1.5.
- User-entered game total plus standard 4.5, 5.5, and 6.5 total-goal probabilities.
- Team goal and team shot thresholds.
- Period-by-period goal averages.
- Skater shots, goals, assists, and points probabilities.
- Projected goalie saves and 20+, 25+, and 30+ save thresholds.
- Optional sportsbook moneyline, total, and puck-line odds comparison, including implied probability, no-vig market probability, model edge, and expected value per $100 stake.

## Important limitations

This is an auditable team/player statistical baseline, not a claim of guaranteed betting advantage. Skater props use independent Poisson approximations from season per-game rates and are not correlated to the simulated team score. Goalie selection is based on season starts unless a player ID is manually supplied. The current roster endpoint does not confirm game-day scratches, injuries, line combinations, or official starting goalies. Verify official team reports and sportsbook prices before placing bets. Overtime/shootout is represented by a 52/48 home-ice proxy. No player prop odds are supplied automatically.

## Tests

The workflow runs offline unit tests before it attempts a live-data simulation. It also runs on pushes to NHL simulator code and workflow files.
