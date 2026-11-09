"""web_prediction_scores / web_backtest_summary on synthetic data (rolled back)."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import insert, text

from engine.db.models import (
    Competition,
    Match,
    MatchStatus,
    ModelRunKind,
    Prediction,
    Season,
    Source,
    Stage,
    Team,
)
from engine.evaluate import metrics
from engine.models.store import create_model_run, set_primary_model

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]

SEASON = "2999-00"
OLD_SEASON = "2000-01"  # before 2026-27: never exposed
PRIMARY = "test_acc_a"
OTHER = "test_acc_b"
FUTURE = datetime(2100, 1, 1, 20, tzinfo=UTC)  # created_at = now() is then before kick-off
PAST = datetime(2000, 1, 1, 20, tzinfo=UTC)  # a prediction made now is after kick-off
FD_IDS = {"A": 990_000_011, "B": 990_000_012}  # no real football-data id
# Shared with apps/web/lib/data/derive.test.ts: both hit definitions must agree on these cases.
HIT_CASES = json.loads((Path(__file__).parent / "fixtures" / "hit_cases.json").read_text("utf-8"))
OUTCOME = {"H": 0, "D": 1, "A": 2}


@pytest.fixture
def conn():
    from engine.db import get_engine

    with get_engine().connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()


@pytest.fixture
def data(conn) -> dict:
    comp = conn.scalar(
        insert(Competition).values(code="TSA", name="test accuracy").returning(Competition.id)
    )
    sid, old_sid = (
        conn.scalar(
            insert(Season)
            .values(competition_id=comp, label=label, format="league_phase")
            .returning(Season.id)
        )
        for label in (SEASON, OLD_SEASON)
    )
    a, b = (
        conn.scalar(
            insert(Team)
            .values(name=f"Test {x}", tla=f"T{x}", fd_team_id=FD_IDS[x])
            .returning(Team.id)
        )
        for x in "AB"
    )
    primary_run = create_model_run(conn, ModelRunKind.PREDICT, {}, None, None, model=PRIMARY)
    other_run = create_model_run(conn, ModelRunKind.PREDICT, {}, None, None, model=OTHER)
    set_primary_model(conn, PRIMARY)

    def match(key: str, season: int, kickoff: datetime, goals: tuple[int, int], md: int) -> int:
        return conn.scalar(
            insert(Match)
            .values(season_id=season, source=Source.MANUAL, source_key=f"test-acc-{key}",
                    stage=Stage.LEAGUE_PHASE, matchday=md, match_date=kickoff.date(),
                    kickoff_utc=kickoff, home_team_id=a, away_team_id=b,
                    status=MatchStatus.FINISHED, home_goals_90=goals[0], away_goals_90=goals[1])
            .returning(Match.id)
        )  # fmt: skip

    def predict(run_id: int, match_id: int, probs: tuple[float, float, float]) -> None:
        conn.execute(
            insert(Prediction).values(
                model_run_id=run_id, match_id=match_id, p_home=probs[0], p_draw=probs[1],
                p_away=probs[2],
            )
        )  # fmt: skip

    cases = {}
    for i, case in enumerate(HIT_CASES):
        mid = match(f"case-{i}", sid, FUTURE, (case["home_goals"], case["away_goals"]), i % 8 + 1)
        predict(primary_run, mid, (case["p_home"], case["p_draw"], case["p_away"]))
        cases[mid] = case
    predict(other_run, next(iter(cases)), (0.2, 0.3, 0.5))

    old = match("old", old_sid, FUTURE, (1, 0), 1)
    late = match("late", sid, PAST, (1, 0), 1)
    for mid in (old, late):
        predict(primary_run, mid, (0.5, 0.3, 0.2))
    return {"cases": cases, "old": old, "late": late, "teams": (a, b)}


def _scores(conn, model: str | None = None) -> dict:
    rows = conn.execute(
        text("SELECT * FROM web_prediction_scores WHERE season = :s"), {"s": SEASON}
    ).all()
    return {r.match_id: r for r in rows if model is None or r.model == model}


def test_prediction_scores_match_python_metrics(conn, data):
    rows = _scores(conn, PRIMARY)
    assert set(rows) == set(data["cases"])  # late (post-kick-off) and old-season are excluded
    for mid, case in data["cases"].items():
        r = rows[mid]
        probs = np.array([[case["p_home"], case["p_draw"], case["p_away"]]])
        y = np.array([OUTCOME[r.outcome]])
        assert r.log_loss == pytest.approx(metrics.log_loss(probs, y))
        assert r.rps == pytest.approx(metrics.rps(probs, y))
        assert r.brier == pytest.approx(metrics.brier(probs, y))
        assert (r.home_goals_90, r.away_goals_90) == (case["home_goals"], case["away_goals"])
        assert (r.home_tla, r.away_tla, r.home_name, r.stage) == (
            "TA", "TB", "Test A", "LEAGUE_PHASE"
        )  # fmt: skip
        assert (r.home_fd_team_id, r.away_fd_team_id) == (FD_IDS["A"], FD_IDS["B"])
        assert r.is_primary is True


def test_prediction_scores_hit_matches_shared_cases(conn, data):
    rows = _scores(conn, PRIMARY)
    for mid, case in data["cases"].items():
        assert rows[mid].hit is case["hit"], case["case"]


def test_prediction_scores_one_row_per_model(conn, data):
    rows = conn.execute(
        text("SELECT model, is_primary FROM web_prediction_scores WHERE season = :s"),
        {"s": SEASON},
    ).all()
    assert sum(r.model == OTHER for r in rows) == 1
    assert {(r.model, r.is_primary) for r in rows} == {(PRIMARY, True), (OTHER, False)}
    set_primary_model(conn, OTHER)
    assert {r.model for r in _scores(conn).values() if r.is_primary} == {OTHER}


def test_prediction_scores_newest_first(conn, data):
    first = conn.execute(text("SELECT season FROM web_prediction_scores LIMIT 1")).scalar_one()
    assert first == SEASON


def _summary(n: int, log_loss: float) -> dict:
    return {"n": n, "log_loss": log_loss, "rps": log_loss / 5, "brier": 0.6, "accuracy": 0.5}


def _bins(offset: float) -> list[dict]:
    return [
        {"lo": b / 10, "hi": (b + 1) / 10, "n": b, "mean_pred": b / 10 + offset,
         "observed": b / 10 if b else None}
        for b in range(10)
    ]  # fmt: skip


@pytest.fixture
def backtests(conn) -> dict:
    scopes = ("2021-22", "2022-23", "overall")

    def elo_metrics(ll: float) -> dict:
        return {
            "test": {
                s: {"elo": _summary(100, ll), "historical": _summary(100, 1.03),
                    "uniform": _summary(100, 1.0986)}
                for s in scopes
            },
            "validation": {"overall": {"elo": _summary(50, 0.9)}},
            "calibration": _bins(0.01),
            "beats_baselines": True,
        }  # fmt: skip

    def run(model: str, payload: dict) -> int:
        return create_model_run(conn, ModelRunKind.BACKTEST, {}, None, payload, model=model)

    stale = run("elo", elo_metrics(0.99))
    elo = run("elo", elo_metrics(0.95))
    poisson = run(
        "poisson",
        {
            "test": {s: _summary(100, 0.96) for s in scopes},
            "calibration": {
                "test": {"home": _bins(0.02), "away": _bins(0.03)},
                "validation": {"home": _bins(0.0), "away": _bins(0.0)},
            },
        },
    )
    run("predict_only", {"n_finished": 1})  # kind=backtest but no test metrics: ignored
    set_primary_model(conn, "elo")
    return {"stale": stale, "elo": elo, "poisson": poisson, "scopes": set(scopes)}


def _backtest_rows(conn, run_ids: set[int]) -> list:
    rows = conn.execute(text("SELECT * FROM web_backtest_summary")).all()
    return [r for r in rows if r.model_run_id in run_ids]


def test_backtest_summary_rows(conn, backtests):
    rows = _backtest_rows(conn, {backtests["stale"], backtests["elo"], backtests["poisson"]})
    assert {r.model_run_id for r in rows} == {backtests["elo"], backtests["poisson"]}
    by = {(r.model, r.scope): r for r in rows}
    assert len(by) == len(rows) == 4 * 3  # elo, poisson, uniform, historical x scopes
    assert {s for _, s in by} == backtests["scopes"]

    elo = by["elo", "overall"]
    assert (elo.role, elo.n, elo.log_loss, elo.is_primary) == ("candidate", 100, 0.95, True)
    assert elo.rps == pytest.approx(0.95 / 5)
    assert elo.calibration_home == _bins(0.01)
    assert elo.calibration_away is None  # not stored for elo backtests

    poisson = by["poisson", "overall"]
    assert (poisson.role, poisson.log_loss, poisson.is_primary) == ("candidate", 0.96, False)
    assert poisson.calibration_home == _bins(0.02)  # the test split, not validation
    assert poisson.calibration_away == _bins(0.03)

    for base, ll in (("uniform", 1.0986), ("historical", 1.03)):
        r = by[base, "overall"]
        assert (r.role, r.model_run_id, r.log_loss, r.n) == ("baseline", backtests["elo"], ll, 100)
        assert (r.calibration_home, r.calibration_away, r.is_primary) == (None, None, False)

    season = by["poisson", "2021-22"]
    assert (season.log_loss, season.calibration_home, season.calibration_away) == (0.96, None, None)


def test_backtest_summary_is_primary(conn, backtests):
    set_primary_model(conn, "poisson")
    rows = _backtest_rows(conn, {backtests["elo"], backtests["poisson"]})
    assert {r.model for r in rows if r.is_primary} == {"poisson"}
