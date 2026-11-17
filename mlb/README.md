# Doug's Elite MLB Model — Initial Foundation

This package is the first MLB implementation in the four-sport repository. It
contains an MLB Stats API schedule/player-stat client, strict confirmed-lineup
validation, a shrinkage-based 1+ hit probability baseline, reproducible Monte
Carlo cross-checks, and unit tests.

## Data source

The adapter uses MLB Stats API endpoints for schedules and player season
statistics. MLB's public API is not a licensed commercial feed; review MLB's
terms and obtain a licensed provider for commercial use or guaranteed service.

## Confirmed lineup contract

A game-specific JSON file must include the exact `gamePk`, `confirmed: true`,
an HTTPS official source URL, a timezone-aware `checked_at_utc` no older than
three hours, nine unique batters in batting order 1–9 for each team, and a
confirmed starting pitcher ID for each team. A probable pitcher is not treated
as a confirmed starter. The model refuses to create player probabilities from
unconfirmed or stale lineups.

See `lineup.example.json` for the shape. Replace all example values with
game-day verified data before use.

## Current model limitations

The 1+ hit baseline shrinks hitter hits per plate appearance toward a league
prior and blends 70% hitter rate with 30% opposing-pitcher hits allowed per
batter faced. Plate-appearance expectations are batting-order priors. It does
not yet incorporate batter/pitcher handedness splits, pitch mix, contact
quality, park/weather, umpire, bullpen exposure, lineup-specific team run
environment, or learned player-level PA distributions. It is not calibrated
and must not be used as an approved wager. The Monte Carlo output is a
consistency check, not a substitute for historical validation.

## Tests

```bash
python -m unittest -v mlb.test_model
```
