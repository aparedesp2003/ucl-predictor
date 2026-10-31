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
sources and approximations are documented in `src/engine/simulate/rules.py`. Each simulated season
adds an N(0, sigma) offset to every team's rating; by default sigma is the spread of Elo changes from
matchday 3 to season end in earlier seasons of the same format (pooled over all seasons if fewer than
two exist). `--sigma 0` freezes ratings. Results go to
`simulation_runs` / `team_simulation_results`.

## Matchday pipeline

```sh
uv run python -m engine.pipeline run [--force] [--dry-run]   # ingest, then predict + simulate if needed
uv run python -m engine.pipeline summary [--run-id N]        # markdown report of a run
```

`run` takes a Postgres advisory lock (a second concurrent run records `locked` and exits 0), ingests
football-data, and compares the payload with the stored matches (new fixtures, newly finished, score /
status / kick-off changes). If the loader inserted or updated any match, or any match's `updated_at` is
newer than the watermark stored by the last `ok` run (before the first one: the latest simulation), it
runs `models predict` (primary + poisson_shrink) and `simulate run` with the default sigma; otherwise it
records `skipped`. Each invocation is a `pipeline_runs` row (`running` until it finishes; a failed step
is `failed` with the error and a non-zero exit). `--dry-run` fetches and reports what would change
without writing anything (no ingest run, no raw cache file). `predictions.created_at` and
`model_runs.created_at` always come from the database clock (see `tests/test_created_at.py`).

Accuracy views: `prediction_scores` (one row per model and finished match with an official
pre-kick-off prediction: outcome from the 90-minute score, log loss, RPS, Brier) and `model_scoreboard`
(per model and season: n, means, accuracy, and the same for a uniform 1/3 forecast on those matches).

`.github/workflows/matchday-pipeline.yml` runs daily at 06:15 UTC and on demand (`force` input), with
`DATABASE_URL` and `FOOTBALL_DATA_TOKEN` from repository secrets; it applies pending migrations
(upgrade only) and writes the run's summary to the job page.
