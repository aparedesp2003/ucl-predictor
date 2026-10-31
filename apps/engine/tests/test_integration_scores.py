"""prediction_scores / model_scoreboard on synthetic matches (rolled-back transaction)."""

import math
import os
from datetime import UTC, datetime

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
from engine.models.store import create_model_run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]

MODEL = "test_scores"
FUTURE = datetime(2100, 1, 1, tzinfo=UTC)  # created_at = now() is then before kick-off
PAST = datetime(2000, 1, 1, tzinfo=UTC)

# (home goals, away goals, p_home, p_draw, p_away, kickoff, status)
MATCHES = [
    (2, 1, 0.5, 0.3, 0.2, FUTURE, MatchStatus.FINISHED),  # H, predicted H
    (1, 1, 0.2, 0.5, 0.3, FUTURE, MatchStatus.FINISHED),  # D, predicted D
    (0, 2, 0.6, 0.25, 0.15, FUTURE, MatchStatus.FINISHED),  # A, predicted H
    (0, 0, 0.4, 0.4, 0.2, FUTURE, MatchStatus.FINISHED),  # D, H/D tie -> predicted H
    (None, None, 0.4, 0.3, 0.3, FUTURE, MatchStatus.SCHEDULED),  # not finished: excluded
    (3, 0, 0.1, 0.1, 0.8, PAST, MatchStatus.FINISHED),  # predicted after kick-off: excluded
]

# Hand-computed per finished match (see the comments above).
LOG_LOSS = [-math.log(0.5), -math.log(0.5), -math.log(0.15), -math.log(0.4)]
RPS = [0.145, 0.065, 0.54125, 0.1]
BRIER = [0.38, 0.38, 1.145, 0.56]


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
def season(conn) -> str:
    comp = conn.scalar(
        insert(Competition).values(code="TST", name="test").returning(Competition.id)
    )
    sid = conn.scalar(
        insert(Season)
        .values(competition_id=comp, label="T-SCORE", format="league_phase")
        .returning(Season.id)
    )
    home, away = (
        conn.scalar(insert(Team).values(name=f"Test {x}").returning(Team.id)) for x in "AB"
    )
    run_id = create_model_run(conn, ModelRunKind.PREDICT, {}, None, None, model=MODEL)
    for i, (hg, ag, ph, pd, pa, ko, status) in enumerate(MATCHES):
        mid = conn.scalar(
            insert(Match)
            .values(season_id=sid, source=Source.MANUAL, source_key=f"test-score-{i}",
                    stage=Stage.LEAGUE_PHASE, matchday=1, match_date=ko.date(), kickoff_utc=ko,
                    home_team_id=home, away_team_id=away, status=status,
                    home_goals_90=hg, away_goals_90=ag)
            .returning(Match.id)
        )  # fmt: skip
        conn.execute(
            insert(Prediction).values(
                model_run_id=run_id, match_id=mid, p_home=ph, p_draw=pd, p_away=pa
            )
        )
    return "T-SCORE"


def test_prediction_scores_rows(conn, season):
    rows = conn.execute(
        text(
            "SELECT outcome, predicted, log_loss, rps, brier, season FROM prediction_scores"
            " WHERE model = :m ORDER BY match_id"
        ),
        {"m": MODEL},
    ).all()
    assert [(r.outcome, r.predicted) for r in rows] == [("H", "H"), ("D", "D"), ("A", "H"),
                                                        ("D", "H")]  # fmt: skip
    assert {r.season for r in rows} == {season}
    for r, ll, rp, br in zip(rows, LOG_LOSS, RPS, BRIER, strict=True):
        assert r.log_loss == pytest.approx(ll, abs=1e-12)
        assert r.rps == pytest.approx(rp, abs=1e-12)
        assert r.brier == pytest.approx(br, abs=1e-12)


def test_model_scoreboard(conn, season):
    row = conn.execute(text("SELECT * FROM model_scoreboard WHERE model = :m"), {"m": MODEL}).one()
    assert (row.season, row.n) == (season, 4)
    assert row.log_loss == pytest.approx(sum(LOG_LOSS) / 4, abs=1e-12)
    assert row.rps == pytest.approx(0.2128125, abs=1e-12)
    assert row.brier == pytest.approx(0.61625, abs=1e-12)
    assert float(row.accuracy) == 0.5
    assert row.uniform_log_loss == pytest.approx(math.log(3), abs=1e-12)
    assert row.uniform_rps == pytest.approx(7 / 36, abs=1e-12)  # H, D, A, D
    assert row.uniform_brier == pytest.approx(2 / 3, abs=1e-12)
    assert float(row.uniform_accuracy) == 0.25


def test_scoreboard_agrees_with_python_metrics(conn, season):
    finished = MATCHES[:4]
    probs = [m[2:5] for m in finished]
    outcomes = [0 if h > a else 1 if h == a else 2 for h, a, *_ in finished]
    row = conn.execute(text("SELECT * FROM model_scoreboard WHERE model = :m"), {"m": MODEL}).one()
    expected = metrics.summary(probs, outcomes)
    uniform = metrics.summary([(1 / 3,) * 3] * 4, outcomes)
    for k in ("log_loss", "rps", "brier", "accuracy"):
        assert float(getattr(row, k)) == pytest.approx(expected[k], abs=1e-12)
        assert float(getattr(row, f"uniform_{k}")) == pytest.approx(uniform[k], abs=1e-12)
