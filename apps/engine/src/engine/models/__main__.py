"""Rating-model CLI.

uv run python -m engine.models elo backtest [--grid]
uv run python -m engine.models elo predict [--defaults]
uv run python -m engine.models poisson backtest
uv run python -m engine.models predict
"""

import argparse
import logging
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from engine.cli import print_table
from engine.db import get_engine
from engine.db.models import ModelRunKind, Team
from engine.evaluate.backtest import (
    DEFAULT_GRID,
    MODELS,
    TEST,
    VALIDATION,
    calibration,
    grid_search,
    predict_upcoming,
    score,
    validation_objective,
    walk_forward,
)
from engine.evaluate.candidates import (
    CANDIDATES,
    build_frame,
    calibration_tables,
    candidate_probs,
    choose_primary,
    fit_calibration,
    predict_scheduled,
    score_candidates,
)
from engine.models.elo import DEFAULT_PARAMS, EloParams
from engine.models.report import print_prob_diff
from engine.models.store import (
    create_model_run,
    get_primary_model,
    kickoff_of,
    latest_backtest_params,
    latest_run,
    load_matches,
    set_primary_model,
    write_predictions,
    write_team_ratings,
)

logger = logging.getLogger("engine.models")

_METRICS = ("log_loss", "rps", "brier", "accuracy")


def _print_scores(title: str, scores: dict) -> None:
    rows = [
        (key, s[model]["n"], model, *(f"{s[model][k]:.4f}" for k in _METRICS))
        for key, s in scores.items()
        for model in MODELS
    ]
    print_table(title, ("season", "n", "model", *_METRICS), rows)


def _beats_baselines(overall: dict) -> bool:
    return all(overall["elo"][k] < overall[b][k] for k in ("log_loss", "rps") for b in MODELS[1:])


def cmd_backtest(args: argparse.Namespace) -> int:
    with get_engine().connect() as conn:
        matches = [m for m in load_matches(conn) if m.season <= TEST[1]]

    metrics: dict = {}
    if args.grid:
        result = grid_search(validation_objective(matches), DEFAULT_GRID)
        params = result.best
        metrics["grid"] = {
            "final_grid": result.grid,
            "rounds": result.rounds,
            "evaluated": len(result.evaluated),
            "best_validation": {"log_loss": result.best_score[0], "rps": result.best_score[1]},
        }
        print_table("final grid", ("param", "values"), [(k, v) for k, v in result.grid.items()])
        print(f"grid rounds: {result.rounds}, combinations evaluated: {len(result.evaluated)}")
    else:
        params = DEFAULT_PARAMS
    print_table("params", ("param", "value"), list(params.to_dict().items()))

    preds, _ = walk_forward(matches, params)
    validation = score(preds, VALIDATION)
    test = score(preds, TEST)
    qualifiers = score(preds, TEST, main=False)
    calib = calibration(preds, TEST)

    _print_scores(f"validation {VALIDATION[0]}..{VALIDATION[1]} (main competition)",
                  {"overall": validation["overall"]})  # fmt: skip
    _print_scores(f"test {TEST[0]}..{TEST[1]} (main competition)", test)
    _print_scores("test qualifiers (QUALIFYING + PLAYOFF_ROUND)", qualifiers)
    print_table(
        "calibration: Elo P(home) on test seasons",
        ("bin", "n", "mean_pred", "observed"),
        [
            (f"{b['lo']:.1f}-{b['hi']:.1f}", b["n"],
             "" if b["mean_pred"] is None else f"{b['mean_pred']:.3f}",
             "" if b["observed"] is None else f"{b['observed']:.3f}")
            for b in calib
        ],
    )  # fmt: skip

    beats = _beats_baselines(test["overall"])
    print(f"\nElo beats both baselines on test log loss and RPS: {'YES' if beats else 'NO'}")

    metrics |= {
        "validation": validation,
        "test": test,
        "test_qualifiers": qualifiers,
        "calibration": calib,
        "beats_baselines": beats,
    }
    train_through = max(m.match_date for m in matches if m.finished)
    with get_engine().begin() as conn:
        run_id = create_model_run(conn, ModelRunKind.BACKTEST, params, train_through, metrics)
    print(f"model_runs id {run_id} (backtest)")
    return 0 if beats else 1


def cmd_predict(args: argparse.Namespace) -> int:
    engine = get_engine()
    with engine.connect() as conn:
        matches = load_matches(conn)
        params: EloParams | None = None if args.defaults else latest_backtest_params(conn)
        names = dict(conn.execute(select(Team.id, Team.name)).all())
    if params is None:
        if not args.defaults:
            sys.exit("no backtest run found; run `elo backtest --grid` first or pass --defaults")
        params = DEFAULT_PARAMS
    print_table("params", ("param", "value"), list(params.to_dict().items()))

    up = predict_upcoming(matches, params)
    if up.train_through is None:
        sys.exit("no finished matches to fit on")
    now = datetime.now(UTC)
    probs = {m.id: p for m, _, p in up.predictions}
    with engine.begin() as conn:
        run_id = create_model_run(
            conn,
            ModelRunKind.PREDICT,
            params,
            up.train_through,
            {"n_finished": sum(m.finished for m in matches), "n_scheduled": len(probs)},
        )
        write_team_ratings(conn, run_id, up.ratings, up.train_through)
        plan = write_predictions(conn, run_id, probs, now)
    print(
        f"model_runs id {run_id} (predict): {len(up.ratings)} ratings as of {up.train_through},"
        f" {len(plan.upserts)} predictions written, {len(plan.skipped_started)} skipped (started)"
    )

    future = [
        (m, d, p) for m, d, p in up.predictions if kickoff_of(m.kickoff_utc, m.match_date) > now
    ]
    if future:
        first = future[0][0]
        nxt = [
            (m, d, p) for m, d, p in future
            if (m.season, m.stage, m.matchday) == (first.season, first.stage, first.matchday)
        ]  # fmt: skip
        print_table(
            f"next matchday: {first.season} {first.stage} matchday {first.matchday}",
            ("kickoff (UTC)", "home", "away", "diff", "p_home", "p_draw", "p_away"),
            [
                (kickoff_of(m.kickoff_utc, m.match_date).strftime("%Y-%m-%d %H:%M"),
                 names[m.home_id], names[m.away_id], f"{d:+.0f}", *(f"{x:.3f}" for x in p))
                for m, d, p in nxt
            ],
        )  # fmt: skip

    top = sorted(up.ratings.items(), key=lambda kv: kv[1], reverse=True)[:20]
    print_table(
        f"top 20 ratings as of {up.train_through}",
        ("#", "team", "rating"),
        [(i, names[t], f"{r:.0f}") for i, (t, r) in enumerate(top, 1)],
    )
    return 0


# --- Poisson candidates, primary model ---------------------------------------------------------


def _calibration_rows(tabs: dict, side: str) -> list[tuple]:
    rows = []
    for i in range(len(tabs[side]["elo"])):
        first = tabs[side]["elo"][i]
        cells = [f"{first['lo']:.1f}-{first['hi']:.1f}"]
        for c in CANDIDATES:
            b = tabs[side][c][i]
            cells.append(f"{b['mean_pred']:.3f}/{b['observed']:.3f} ({b['n']})" if b["n"] else "-")
        rows.append(tuple(cells))
    return rows


def _print_candidates(title: str, scores: dict) -> None:
    rows = [
        (key, s[c]["n"], c, *(f"{s[c][k]:.4f}" for k in _METRICS))
        for key, s in scores.items()
        for c in CANDIDATES
    ]
    print_table(title, ("season", "n", "candidate", *_METRICS), rows)


def _fmt(p) -> str:
    return "/".join(f"{x:.3f}" for x in p)


def cmd_poisson_backtest(args: argparse.Namespace) -> int:
    with get_engine().connect() as conn:
        matches = [m for m in load_matches(conn) if m.season <= TEST[1]]
        params = latest_backtest_params(conn)
    if params is None:
        sys.exit("no Elo backtest run found; run `elo backtest --grid` first")
    print_table(
        "Elo params (latest elo backtest)", ("param", "value"), list(params.to_dict().items())
    )

    preds, _ = walk_forward(matches, params)
    frame = build_frame(preds, params)
    cal = fit_calibration(frame)
    probs = candidate_probs(frame, cal)
    print(f"\ntemperature T = {cal.temperature:.4f}, shrink s = {cal.shrink:.4f} (validation fit)")

    validation = score_candidates(frame, probs, VALIDATION)
    test = score_candidates(frame, probs, TEST)
    qualifiers = score_candidates(frame, probs, TEST, main=False)
    calib = {
        "validation": calibration_tables(frame, probs, VALIDATION),
        "test": calibration_tables(frame, probs, TEST),
    }
    _print_candidates("validation (main competition)", {"overall": validation["overall"]})
    _print_candidates("test (main competition)", test)
    _print_candidates("test qualifiers", {"overall": qualifiers["overall"]})
    for split in ("validation", "test"):
        for side in ("home", "away"):
            print_table(
                f"calibration {split} P({side} win): mean_pred/observed (n)",
                ("bin", *CANDIDATES),
                _calibration_rows(calib[split], side),
            )
    chosen, primary, gate = choose_primary(validation, test)
    print(
        f"\nchosen by validation log loss: {chosen};"
        f" test gate vs elo: {'pass' if gate else 'FAIL'}; primary model: {primary}"
    )

    run_params = {
        "elo": params.to_dict(),
        "temperature": cal.temperature,
        "shrink": cal.shrink,
        "loso_temperature": cal.loso_temperature,
        "loso_shrink": cal.loso_shrink,
    }
    selection = {"chosen": chosen, "primary": primary, "gate_passed": gate}
    comparison = {
        "validation": validation["overall"],
        "test": test["overall"],
        "test_qualifiers": qualifiers["overall"],
    }
    train_through = max(m.match_date for m in matches if m.finished)
    ids = {}
    with get_engine().begin() as conn:
        for c in CANDIDATES[1:]:  # elo's own backtest run comes from `elo backtest`
            metrics = {
                "validation": {k: v[c] for k, v in validation.items()},
                "test": {k: v[c] for k, v in test.items()},
                "test_qualifiers": {k: v[c] for k, v in qualifiers.items()},
                "calibration": {
                    split: {side: t[side][c] for side in t} for split, t in calib.items()
                },
                "comparison": comparison,
                "selection": selection,
            }
            ids[c] = create_model_run(
                conn, ModelRunKind.BACKTEST, run_params, train_through, metrics, model=c
            )
        set_primary_model(conn, primary)
    print("model_runs (backtest):", ", ".join(f"{c}={i}" for c, i in ids.items()))
    print(f"settings.primary_model = {primary}")
    return 0


def cmd_predict_primary(args: argparse.Namespace) -> int:
    engine = get_engine()
    with engine.connect() as conn:
        matches = load_matches(conn)
        params = latest_backtest_params(conn)
        poisson_run = latest_run(conn, "poisson_shrink", ModelRunKind.BACKTEST)
        primary = get_primary_model(conn)
        names = dict(conn.execute(select(Team.id, Team.name)).all())
    if params is None or poisson_run is None:
        sys.exit("run `elo backtest --grid` and `poisson backtest` first")
    temperature, shrink = poisson_run[1]["temperature"], poisson_run[1]["shrink"]
    print(f"primary model: {primary}; also tracking poisson_shrink (s = {shrink:.4f})")

    up = predict_upcoming(matches, params)
    if up.train_through is None:
        sys.exit("no finished matches to fit on")
    sched = predict_scheduled(up, params, temperature, shrink)
    now = datetime.now(UTC)
    run_params = {
        "elo": params.to_dict(),
        "temperature": temperature,
        "shrink": shrink,
        "poisson": {s: f.to_dict() for s, f in sched.fits.items()},
        "calibration_run_id": poisson_run[0],
    }
    counts = {"n_finished": sum(m.finished for m in matches), "n_scheduled": len(sched.matches)}
    probs = {
        model: {
            m.id: tuple(float(x) for x in p)
            for m, p in zip(sched.matches, sched.probs[model], strict=True)
        }
        for model in sched.probs
    }
    with engine.begin() as conn:
        for model in dict.fromkeys([primary, "poisson_shrink"]):
            run_id = create_model_run(
                conn, ModelRunKind.PREDICT, run_params, up.train_through, counts, model=model
            )
            write_team_ratings(conn, run_id, up.ratings, up.train_through)
            plan = write_predictions(conn, run_id, probs[model], now)
            print(
                f"model_runs id {run_id} ({model} predict): {len(plan.upserts)} predictions"
                f" written, {len(plan.skipped_started)} skipped (started)"
            )

    future = [m for m in sched.matches if kickoff_of(m.kickoff_utc, m.match_date) > now]
    if future:
        first = future[0]
        key = (first.season, first.stage, first.matchday)
        print_table(
            f"next matchday: {first.season} {first.stage} matchday {first.matchday}",
            ("kickoff (UTC)", "home", "away", f"{primary} H/D/A", "poisson_shrink H/D/A"),
            [
                (kickoff_of(m.kickoff_utc, m.match_date).strftime("%Y-%m-%d %H:%M"),
                 names[m.home_id], names[m.away_id],
                 _fmt(probs[primary][m.id]), _fmt(probs["poisson_shrink"][m.id]))
                for m in future
                if (m.season, m.stage, m.matchday) == key
            ],
        )  # fmt: skip

    top = sorted(up.ratings.items(), key=lambda kv: kv[1], reverse=True)[:20]
    print_table(
        f"top 20 ratings as of {up.train_through}",
        ("#", "team", "rating"),
        [(i, names[t], f"{r:.0f}") for i, (t, r) in enumerate(top, 1)],
    )
    with engine.connect() as conn:
        print_prob_diff(conn, names, probs["elo"], probs["poisson_shrink"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.models")
    models = parser.add_subparsers(dest="model", required=True)
    elo = models.add_parser("elo", help="Elo ratings + multinomial outcome model")
    sub = elo.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest", help="walk-forward backtest; writes a backtest model run")
    bt.add_argument("--grid", action="store_true", help="tune params on validation seasons")
    bt.set_defaults(func=cmd_backtest)

    pr = sub.add_parser("predict", help="fit on all finished matches, predict scheduled ones")
    pr.add_argument(
        "--defaults", action="store_true", help="use default params, not the latest backtest's"
    )
    pr.set_defaults(func=cmd_predict)

    pois = models.add_parser("poisson", help="Poisson goals model and calibration candidates")
    psub = pois.add_subparsers(dest="command", required=True)
    pbt = psub.add_parser("backtest", help="compare candidates, write runs, set the primary model")
    pbt.set_defaults(func=cmd_poisson_backtest)

    top = models.add_parser("predict", help="primary model + poisson_shrink for scheduled matches")
    top.set_defaults(func=cmd_predict_primary)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
