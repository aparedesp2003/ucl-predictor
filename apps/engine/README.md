# engine

Python data/ML engine for the UCL predictor. See the repo-root README for setup.

## Data ingest

```sh
uv run alembic upgrade head
uv run python -m engine.ingest football-data                        # current season (football-data.org)
uv run python -m engine.ingest openfootball --from 2011-12 --to 2025-26  # past seasons (Football.TXT)
uv run python -m engine.ingest report                               # coverage + data-quality checks
```

Load football-data first: it creates teams with `fd_team_id`, which openfootball names then resolve
against. Raw downloads are cached under `data/raw/` (git-ignored). Team names that normalization
cannot match go in `src/engine/ingest/team_overrides.csv`, each with a reason.

Tests: `uv run pytest` (no network/DB); `RUN_INTEGRATION=1 uv run pytest -m integration` hits the DB
inside a rolled-back transaction.

## Elo model

```sh
uv run python -m engine.models elo backtest --grid   # tune on 2015-16..2020-21, report 2021-22..2025-26
uv run python -m engine.models elo predict           # ratings + predictions for every scheduled match
```

`backtest` walks forward through every finished match: each prediction uses Elo ratings from strictly
earlier matches and an outcome model (multinomial logistic regression on the rating difference) fitted
on earlier seasons only. 2011-12..2014-15 are burn-in. Main-competition matches are scored against a
uniform and a historical-rate baseline; qualifiers are reported separately. `--grid` extends any
parameter chosen on a grid edge outward and re-searches until the choice is interior. Each run writes a
`model_runs` row (`kind` = backtest | predict).

`predict` uses the params of the latest backtest run (`--defaults` to override), writes final
`team_ratings` and `predictions`, and prints the next matchday and the top 20 ratings. A prediction for a
match that has kicked off is never changed; the `official_predictions` view returns, per match, the
latest prediction created before kick-off.

## Poisson model, calibration and primary model

```sh
uv run python -m engine.models poisson backtest   # compare candidates, set settings.primary_model
uv run python -m engine.models predict            # primary model + poisson_shrink for scheduled matches
```

Candidates share the Elo walk-forward: `elo`, `poisson` (Elo-driven Poisson + Dixon-Coles, refitted
each season on earlier seasons), `poisson_cal` (temperature scaling), `poisson_shrink` (rating slope
scaled by `s`) and `blend` (mean of elo and poisson_cal). T and s are fitted on validation seasons
(leave-one-season-out when scoring validation). The primary is the lowest validation log loss and must
not lose to Elo on test log loss. `official_predictions` holds the latest pre-kick-off prediction per
(model, match); `official_primary_predictions` keeps the model named in `settings.primary_model`.

## Season simulator

```sh
uv run python -m engine.simulate run [--n 10000] [--seed 42]
```

Samples the remaining league-phase scorelines from the latest `poisson_shrink` predict run (ratings
frozen), ranks the 36 teams with the 2026/27 tiebreakers, then plays the knockout bracket. Rules,
sources and approximations are documented in `src/engine/simulate/rules.py`. Results go to
`simulation_runs` / `team_simulation_results`.
