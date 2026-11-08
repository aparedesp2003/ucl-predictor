"""The merge_split_teams migration on a synthetic split (rolled-back transaction; DEV at head)."""

import importlib.util
import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import insert, select, text

from engine.db.models import (
    Competition,
    Match,
    MatchStatus,
    ModelRunKind,
    Prediction,
    Season,
    SeasonFormat,
    Source,
    Stage,
    Team,
    TeamAlias,
    TeamRating,
)
from engine.ingest.load import build_resolver
from engine.models.store import create_model_run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "b4fdcdb0088b_merge_split_teams.py"
)
FD = 990001  # far outside football-data's id range
ALIAS = "ZZ Test Club"


def _migration():
    spec = importlib.util.spec_from_file_location("merge_split_teams", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conn():
    from engine.db import get_engine

    with get_engine().connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()


def _team(conn, name, fd_team_id=None, country="ZZZ") -> int:
    return conn.scalar(
        insert(Team).values(name=name, country=country, fd_team_id=fd_team_id).returning(Team.id)
    )


def _match(conn, season_id, key, home, away, day) -> int:
    return conn.scalar(
        insert(Match)
        .values(
            season_id=season_id, source=Source.MANUAL, source_key=key,
            stage=Stage.GROUP_STAGE, match_date=date(1990, 10, day), home_team_id=home,
            away_team_id=away, status=MatchStatus.FINISHED, home_goals_90=1, away_goals_90=0,
            updated_at=datetime(2000, 1, 1, tzinfo=UTC),
        )
        .returning(Match.id)
    )  # fmt: skip


@pytest.fixture
def split(conn):
    """canon (fd 990001) and dup (openfootball alias only) are one club; other is unrelated."""
    comp = conn.scalar(select(Competition.id).where(Competition.code == "CL"))
    season = conn.scalar(
        insert(Season)
        .values(competition_id=comp, label="1990-91", format=SeasonFormat.GROUP_STAGE)
        .returning(Season.id)
    )
    canon = _team(conn, "ZZ Test Club Rotterdam", FD)
    dup = _team(conn, ALIAS)
    other = _team(conn, "ZZ Other")
    conn.execute(
        insert(TeamAlias).values(
            [
                {
                    "team_id": canon,
                    "source": Source.FOOTBALL_DATA,
                    "alias": "ZZ Test Club Rotterdam",
                },
                {"team_id": dup, "source": Source.OPENFOOTBALL, "alias": ALIAS},
                {"team_id": other, "source": Source.OPENFOOTBALL, "alias": "ZZ Other"},
            ]
        )
    )
    m_home = _match(conn, season, "zz-merge-1", dup, other, 1)
    m_away = _match(conn, season, "zz-merge-2", other, dup, 8)
    m_other = _match(conn, season, "zz-merge-3", other, canon, 15)
    run = create_model_run(conn, ModelRunKind.BACKTEST, {}, None, None, model="zz_test")
    as_of = date(1990, 12, 1)
    conn.execute(
        insert(TeamRating).values(
            [
                {"model_run_id": run, "team_id": dup, "rating": 1450.0, "as_of_date": as_of},
                {"model_run_id": run, "team_id": canon, "rating": 1500.0, "as_of_date": as_of},
            ]
        )
    )
    conn.execute(
        insert(Prediction).values(
            model_run_id=run, match_id=m_home, p_home=0.5, p_draw=0.3, p_away=0.2
        )
    )
    return {
        "canon": canon, "dup": dup, "other": other, "run": run,
        "m_home": m_home, "m_away": m_away, "m_other": m_other,
    }  # fmt: skip


def _snapshot(conn, ids) -> dict:
    """Everything the merge must leave alone, plus the rows it moves."""
    q = lambda sql: conn.execute(text(sql), ids).all()  # noqa: E731
    return {
        "matches": q(
            "SELECT id, home_team_id, away_team_id, updated_at FROM matches"
            " WHERE id IN (:m_home, :m_away, :m_other) ORDER BY id"
        ),
        "aliases": q(
            "SELECT id, team_id, source, alias FROM team_aliases"
            " WHERE team_id IN (:canon, :dup, :other) ORDER BY id"
        ),
        "teams": q(
            "SELECT id, name, country, fd_team_id, merged_into_team_id FROM teams"
            " WHERE id IN (:canon, :dup, :other) ORDER BY id"
        ),
        "ratings": q("SELECT * FROM team_ratings WHERE model_run_id = :run ORDER BY id"),
        "predictions": q("SELECT * FROM predictions WHERE model_run_id = :run ORDER BY id"),
    }


def test_merge_moves_rows_and_is_idempotent(conn, split):
    mig = _migration()
    before = _snapshot(conn, split)

    counts = mig.merge_pairs(conn, [(FD, ALIAS)])
    assert counts == {
        ALIAS: {"team_aliases.team_id": 1, "matches.home_team_id": 1, "matches.away_team_id": 1}
    }

    after = _snapshot(conn, split)
    canon, dup, other = split["canon"], split["dup"], split["other"]
    moved = {m.id: m for m in after["matches"]}
    assert (moved[split["m_home"]].home_team_id, moved[split["m_home"]].away_team_id) == (
        canon,
        other,
    )
    assert (moved[split["m_away"]].home_team_id, moved[split["m_away"]].away_team_id) == (
        other,
        canon,
    )
    old = {m.id: m for m in before["matches"]}
    for mid in (split["m_home"], split["m_away"]):
        assert moved[mid].updated_at > old[mid].updated_at  # the pipeline sees the change
    assert moved[split["m_other"]] == old[split["m_other"]]  # unrelated match untouched

    assert {(a.alias, a.team_id) for a in after["aliases"]} == {
        ("ZZ Test Club Rotterdam", canon), (ALIAS, canon), ("ZZ Other", other),
    }  # fmt: skip
    teams = {t.id: t for t in after["teams"]}
    assert teams[dup].merged_into_team_id == canon  # the row stays, marked
    assert teams[canon].merged_into_team_id is None
    assert teams[other] == {t.id: t for t in before["teams"]}[other]
    assert after["ratings"] == before["ratings"]  # past runs stay reproducible
    assert after["predictions"] == before["predictions"]

    logged = conn.execute(
        text(
            "SELECT table_name, column_name, row_id FROM team_merge_moves WHERE merged_team_id = :d"
        ),
        {"d": dup},
    ).all()
    assert len(logged) == 3

    # the resolver no longer sees the duplicate; its alias now leads to the canonical team
    resolver = build_resolver(conn)
    assert resolver.resolve(Source.OPENFOOTBALL, ALIAS, "ZZZ").team_id == canon
    assert not [p for p in resolver.possible_duplicates() if p[0] == "ZZZ" and ALIAS in p]

    # rerun: nothing left to merge
    assert mig.merge_pairs(conn, [(FD, ALIAS)]) == {}
    assert _snapshot(conn, split) == after


def test_absent_pair_is_a_noop(conn, split):
    mig = _migration()
    before = _snapshot(conn, split)
    assert mig.merge_pairs(conn, [(FD + 1, ALIAS), (FD, "ZZ No Such Alias")]) == {}
    assert _snapshot(conn, split) == before


def test_inconsistent_pair_raises(conn, split):
    conn.execute(text("UPDATE teams SET country = 'ZZY' WHERE id = :dup"), {"dup": split["dup"]})
    with pytest.raises(RuntimeError, match="countries"):
        _migration().merge_pairs(conn, [(FD, ALIAS)])


def test_unmerge_reverses_exactly(conn, split):
    mig = _migration()
    before = _snapshot(conn, split)
    mig.merge_pairs(conn, [(FD, ALIAS)])
    assert mig.unmerge(conn, [split["dup"]]) == [split["dup"]]

    after = _snapshot(conn, split)
    strip = lambda rows: [r[:3] for r in rows]  # noqa: E731  (updated_at is bumped again)
    assert strip(after["matches"]) == strip(before["matches"])
    for key in ("aliases", "teams", "ratings", "predictions"):
        assert after[key] == before[key]
    assert not conn.scalar(
        text("SELECT count(*) FROM team_merge_moves WHERE merged_team_id = :d"), {"d": split["dup"]}
    )


def test_unmerge_refuses_when_not_exact(conn, split):
    mig = _migration()
    mig.merge_pairs(conn, [(FD, ALIAS)])
    conn.execute(
        text("UPDATE matches SET home_team_id = :o WHERE id = :m"),
        {"o": split["other"], "m": split["m_home"]},
    )  # a later correction moved one of the logged rows elsewhere
    with pytest.raises(RuntimeError, match="cannot reverse the team merge exactly"):
        mig.unmerge(conn, [split["dup"]])
