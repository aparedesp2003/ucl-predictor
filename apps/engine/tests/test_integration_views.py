"""Per-model official prediction views against the real database (rolled-back transaction)."""

import os
from datetime import timedelta

import pytest
from sqlalchemy import insert, select, text

from engine.db.models import Match, MatchStatus, ModelRunKind, Prediction
from engine.models.store import create_model_run, set_primary_model

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


@pytest.fixture
def match(conn):
    return conn.execute(
        select(Match.id, Match.kickoff_utc)
        .where(Match.status == MatchStatus.FINISHED, Match.kickoff_utc.is_not(None))
        .order_by(Match.id)
        .limit(1)
    ).one()


def _run(conn, model: str) -> int:
    return create_model_run(conn, ModelRunKind.PREDICT, {}, None, None, model=model)


def _pred(conn, run_id, match_id, p_home, created_at):
    rest = (1 - p_home) / 2
    conn.execute(
        insert(Prediction).values(
            model_run_id=run_id, match_id=match_id, p_home=p_home, p_draw=rest, p_away=rest,
            created_at=created_at,
        )
    )  # fmt: skip


def _official(conn, view: str, match_id: int) -> dict[str, tuple[int, float]]:
    rows = conn.execute(
        text(f"SELECT model, model_run_id, p_home FROM {view} WHERE match_id = :m"),
        {"m": match_id},
    )
    return {model: (run_id, p) for model, run_id, p in rows}


def test_models_do_not_shadow_each_other(conn, match):
    before = match.kickoff_utc - timedelta(hours=2)
    elo, shrink = _run(conn, "test_elo"), _run(conn, "test_shrink")
    _pred(conn, elo, match.id, 0.5, before)
    _pred(conn, shrink, match.id, 0.4, before + timedelta(hours=1))  # newer, other model
    official = _official(conn, "official_predictions", match.id)
    assert official["test_elo"] == (elo, 0.5)
    assert official["test_shrink"] == (shrink, 0.4)


def test_post_kickoff_rows_never_official_for_any_model(conn, match):
    ko = match.kickoff_utc
    for model in ("test_elo", "test_shrink"):
        early, late = _run(conn, model), _run(conn, model)
        _pred(conn, early, match.id, 0.5, ko - timedelta(hours=1))
        _pred(conn, late, match.id, 0.9, ko + timedelta(minutes=1))
    official = _official(conn, "official_predictions", match.id)
    assert {m: p for m, (_, p) in official.items() if m.startswith("test_")} == {
        "test_elo": 0.5,
        "test_shrink": 0.5,
    }


def test_primary_view_follows_settings(conn, match):
    before = match.kickoff_utc - timedelta(hours=1)
    _pred(conn, _run(conn, "test_elo"), match.id, 0.5, before)
    _pred(conn, _run(conn, "test_shrink"), match.id, 0.4, before)
    set_primary_model(conn, "test_elo")
    assert _official(conn, "official_primary_predictions", match.id) == {
        "test_elo": _official(conn, "official_predictions", match.id)["test_elo"]
    }
    set_primary_model(conn, "test_shrink")
    assert set(_official(conn, "official_primary_predictions", match.id)) == {"test_shrink"}
