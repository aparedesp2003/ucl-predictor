"""Elo backtest and prediction persistence against the real database, inside a rolled-back
transaction."""

import math
import os
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from engine.db.models import Match, MatchStatus, ModelRun, ModelRunKind, Prediction
from engine.evaluate.backtest import score, walk_forward
from engine.models.elo import DEFAULT_PARAMS
from engine.models.store import (
    PostKickoffUpdateError,
    create_model_run,
    load_matches,
    write_predictions,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]


@pytest.fixture
def conn():
    from engine.db import get_engine

    with get_engine().connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()


def _finished_match(conn, with_kickoff: bool = True):
    row = conn.execute(
        select(Match.id, Match.kickoff_utc, Match.match_date)
        .where(Match.status == MatchStatus.FINISHED, Match.kickoff_utc.is_not(None))
        .order_by(Match.id)
        .limit(1)
    ).one()
    if with_kickoff:
        return row
    # Every loaded match has a kick-off time; drop one (rolled back) to cover the NULL fallback.
    conn.execute(update(Match).where(Match.id == row.id).values(kickoff_utc=None))
    return row.id, None, row.match_date


def _run(conn) -> int:
    return create_model_run(conn, ModelRunKind.PREDICT, DEFAULT_PARAMS, None, None)


def _insert_pred(conn, run_id, match_id, probs, created_at):
    conn.execute(
        insert(Prediction).values(
            model_run_id=run_id,
            match_id=match_id,
            p_home=probs[0],
            p_draw=probs[1],
            p_away=probs[2],
            created_at=created_at,
        )
    )


def test_backtest_small_range(conn):
    matches = [m for m in load_matches(conn) if m.season <= "2013-14"]
    preds, state = walk_forward(matches, DEFAULT_PARAMS, score_from="2013-14")
    overall = score(preds, ("2013-14", "2013-14"))["overall"]
    assert overall["elo"]["n"] == 125
    assert all(math.isfinite(overall[m]["log_loss"]) for m in overall)
    assert overall["uniform"]["log_loss"] == pytest.approx(math.log(3))
    assert len(state.ratings) > 32


def test_writer_refuses_post_kickoff_update(conn):
    match_id, kickoff, _ = _finished_match(conn)
    run_id = _run(conn)
    plan = write_predictions(conn, run_id, {match_id: (0.5, 0.3, 0.2)}, now=kickoff - timedelta(1))
    assert list(plan.upserts) == [match_id]
    with pytest.raises(PostKickoffUpdateError):
        write_predictions(conn, run_id, {match_id: (0.4, 0.3, 0.3)})
    stored = conn.execute(
        select(Prediction.p_home).where(
            Prediction.model_run_id == run_id, Prediction.match_id == match_id
        )
    ).scalar_one()
    assert stored == 0.5


@pytest.mark.parametrize("with_kickoff", [True, False])
def test_newer_post_kickoff_prediction_never_becomes_official(conn, with_kickoff):
    match_id, kickoff, match_date = _finished_match(conn, with_kickoff)
    kickoff = kickoff or datetime.combine(match_date, time.min, tzinfo=UTC)
    run_a, run_b = _run(conn), _run(conn)
    _insert_pred(conn, run_a, match_id, (0.5, 0.3, 0.2), kickoff - timedelta(hours=1))
    _insert_pred(conn, run_b, match_id, (0.1, 0.1, 0.8), kickoff + timedelta(hours=1))
    official = conn.execute(
        text("SELECT model_run_id, p_home FROM official_predictions WHERE match_id = :m"),
        {"m": match_id},
    ).one()
    assert tuple(official) == (run_a, 0.5)


def test_model_run_with_predictions_cannot_be_deleted(conn):
    match_id, kickoff, _ = _finished_match(conn)
    run_id = _run(conn)
    _insert_pred(conn, run_id, match_id, (0.5, 0.3, 0.2), kickoff - timedelta(hours=1))
    with pytest.raises(IntegrityError), conn.begin_nested():
        conn.execute(delete(ModelRun).where(ModelRun.id == run_id))


def test_probabilities_must_sum_to_one(conn):
    match_id, kickoff, _ = _finished_match(conn)
    run_id = _run(conn)
    with pytest.raises(IntegrityError), conn.begin_nested():
        _insert_pred(conn, run_id, match_id, (0.5, 0.3, 0.3), kickoff - timedelta(hours=1))
