# Doug's Elite NHL Simulator

A reproducible NHL matchup Monte Carlo baseline, launched through GitHub Actions.

## Run it
1. Open **Actions** in this repository.
2. Select **Run Doug's Elite NHL Simulator**.
3. Choose the home and away team abbreviations, select trial count (default 100,000), and run the workflow.
4. Download the `dougs-elite-nhl-simulation-results` artifact.

## Model v1
- Pulls team goals-for, goals-against, shots-for, shots-against, power-play, penalty-kill and faceoff rates from the public NHL club-stats endpoint when available.
- Simulates goals and shots using reproducible Poisson Monte Carlo draws.
- Reports moneyline proxy, regulation win rates, expected goals/shots, team goal thresholds, and game total goal probabilities.
- Uses transparent league-average fallback values if the NHL stats endpoint is unavailable; the output labels the source used.

## Important limitations
This first version is a team-market baseline, not a fully calibrated betting model. Regulation ties are split 50/50 for the moneyline proxy. Overtime/shootout, confirmed starting goalies, goalie save percentage, line combinations, injuries, rest/travel, player props, and sportsbook prices/vig are not yet incorporated. Do not treat probabilities as guaranteed outcomes.
