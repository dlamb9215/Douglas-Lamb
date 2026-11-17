# Four-Sport Betting Model Audit — 2026-11-17

Repository: `dlamb9215/Douglas-Lamb`
Audit branch: `elite-four-model-upgrade`
Base branch: `main`

## Executive status

This is an initial repository audit, not a certification of betting performance. Existing code and workflow documentation were inspected on the default branch. No live game simulation was run as part of this audit.

| Sport | Existing foundation observed | Material blockers before betting approval |
|---|---|---|
| NFL | Drive-based simulator, team-stat comparison, player pipeline, game-day confirmation file, forecast ledger, market quote validation, shared BET/PASS layer | Out-of-sample calibration remains blocked; official inactives and active starters must be supplied and verified; workload inputs such as routes/red-zone usage are not consistently available |
| NBA | Monte Carlo engine, data preflight, confirmed-lineup input contract, market adapter, prediction ledger and settlement workflow | Market-specific calibration deliberately false; lineup/minute inputs are manually supplied; official injury report and two-sided current odds required |
| MLB | No top-level MLB package, simulator entry point, MLB-specific workflow, or MLB tests were visible in the repository root listing | Treat as an incomplete/missing standalone model until a full package, data adapters, simulation engine, tests, ledger and workflow are implemented |
| NHL | Dedicated `nhl/elite.py` and `nhl/simulator.py` package, current-season NHL API data, team-level Monte Carlo, optional goalie selection, workflow and tests | Current elite model is primarily team-level; roster-season goalie selection is not the same as a confirmed game starter, skater props are not correlated with team score, and there is no NHL historical calibration ledger or shared BET/PASS integration |

## Confirmed repository findings

1. `BETTING_ENGINE_UPGRADE.md` documents a shared decision layer currently integrated with NBA and NFL. Its gates require fresh two-sided odds, data readiness, official availability confirmation, out-of-sample calibration, minimum edge and expected value.
2. The same document explicitly says NBA/NFL market calibration flags remain false until chronological holdout ledgers are reviewed. A successful CI run or a high trial count is not evidence of predictive accuracy.
3. `NFL_BETTING_READINESS.md` says the NFL smoke test runs 100,000 trials but is not betting-readiness approval. It also says routes/red-zone opportunity counts may be unavailable and final game-day confirmations are separate from roster/injury feeds.
4. `README-NHL-ELITE.md` describes important NHL limitations: season-start goalie selection unless manually overridden, no automatic official game-day scratches/line combinations, independent Poisson player props, and an overtime/shootout proxy.
5. Direct inspection of `nhl_simulator.py` shows a league-average fallback when the live NHL club-stats request fails. This must be reconciled with the README's fail-closed claim before a betting-grade release.
6. The root listing contains no standalone `mlb/` package or MLB workflow/test entry points. MLB is therefore a priority build, not a model to label complete based on prior conversation alone.

## Release architecture required for all four sports

- Keep sport-specific feature engineering and probability models separate.
- Use one shared, sport-neutral decision layer for quote freshness, American-odds conversion, no-vig probabilities, push-aware EV, edge, stake-risk caps, and BET/PASS blockers.
- Require source provenance and retrieval timestamps for every input. Fail closed on missing or stale critical data.
- Record immutable pregame predictions before start time; settle only against exact event identifiers and verified final results.
- Keep training, calibration, and final test periods chronologically separated. Never tune on the final holdout.
- Report sample sizes, Brier score, log loss, reliability bins, ROI with uncertainty, and closing-line value by sport and market.
- Keep player-prop joint outcomes correlated through shared minutes/usage/game scripts rather than multiplying marginal probabilities.
- Do not auto-approve picks from raw model confidence. BET is available only after market-specific calibration and live-data gates pass.

## Sport-specific build requirements

### NFL
Preserve the existing team-vs-team offense/defense report and drive simulation. Improve player opportunity data (snaps, routes, targets, carries, red-zone usage), game-script scenarios, official inactive verification, prop distribution checks, and chronological market-specific validation.

### NBA
Preserve possession/efficiency and Four Factors modeling. Improve official injury-report ingestion, confirmed starters, minute distributions and rotation scenarios, correlated player outcomes, odds coverage, and ledger completeness. Validate spreads, totals, moneylines and each prop family independently.

### MLB
Build a complete package around schedule/game IDs, probable pitchers, confirmed lineups/batting order, hitter/pitcher handedness splits, plate-appearance opportunity, contact/quality-of-contact features, bullpen usage, park and weather context. Model 1+ hit, total bases, strikeouts and game markets separately. No hitter prop may pass without a confirmed lineup and batting-order position. Track pitcher changes and lineup scratches.

### NHL
Remove silent league-average fallback for required live team inputs. Require explicit goalie status (confirmed vs projected), lineup/scratch verification, special-teams and goalie workload inputs, and team/player models that preserve game-level dependence. Replace proxy overtime assumptions with an explicitly validated overtime/shootout component. Add the shared decision engine and historical ledger.

## Completion checklist

- [x] Initial four-sport repository audit documented on this branch\n- [x] Shared BET/PASS decision gate expanded to accept NFL, NBA, MLB and NHL labels (sport-specific integrations and validation still required)\n- [x] Legacy root NHL simulator changed to fail closed on live-data failure, with regression test\n- [x] Shared betting and NHL test suites added to general CI workflow\n- [x] Initial MLB schedule/season-stat adapter, confirmed-lineup validator, 1+ hit baseline, tests, README and manual workflow added\n- [x] Shared two-way decision adapter tests extended to MLB and NHL; calibration remains a hard blocker\n- [ ] NFL audit, code review, tests and data-readiness contract complete
- [ ] NBA audit, code review, tests and data-readiness contract complete
- [ ] MLB package expanded with handedness/Statcast/bullpen/park features, sportsbook integration, prediction/settlement ledger and historical validation
- [ ] NHL fail-closed behavior, goalie/lineup data, tests and ledger complete
- [ ] Shared cross-sport odds/EV/decision layer supports NFL, NBA, MLB and NHL
- [ ] Every sport/market has chronological backtesting and calibration review
- [ ] Workflow artifacts include input provenance, model version, trial count, seed, predictions and blockers
- [ ] Full CI and four-sport integration tests pass
- [ ] Betting release remains blocked wherever evidence or data is insufficient

## Important

“Elite” means auditable, calibrated, robust and demonstrably useful against market prices. It does not mean guaranteed wins or profit. Simulation volume reduces sampling noise; it cannot repair biased inputs, poor assumptions, or uncalibrated probabilities.
