"""Advisory lock and run log against the real database. Rows written here are deleted afterwards."""

import os
from dataclasses import replace

import pytest
from sqlalchemy import delete, select

from engine.db.models import PipelineRun, PipelineStatus, PipelineTrigger
from engine.pipeline import orchestrator
from engine.pipeline.changes import IngestResult
from engine.pipeline.db import DbRunLog, DbSteps, changed_since_last_ok
from engine.pipeline.summary import load_report, render
from tests.test_pipeline_orchestrator import FakeSteps

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]

# A key of its own, so the test never blocks (or is blocked by) a real pipeline run.
TEST_LOCK_KEY = 0x55434C51


class Steps(FakeSteps):
    """FakeSteps without a made-up ingest_runs id (pipeline_runs.ingest_run_id is a foreign key)."""

    def ingest(self, dry_run: bool) -> IngestResult:
        return replace(super().ingest(dry_run), run_id=None)


@pytest.fixture
def engine():
    from engine.db import get_engine

    return get_engine()


@pytest.fixture
def cleanup(engine):
    ids: list[int] = []
    yield ids
    with engine.begin() as conn:
        conn.execute(delete(PipelineRun).where(PipelineRun.id.in_(ids)))


def test_second_concurrent_run_records_locked(engine, cleanup):
    holder = DbRunLog(engine, TEST_LOCK_KEY)
    assert holder.try_lock()
    try:
        steps = Steps(updated=1)
        out = orchestrator.run(steps, DbRunLog(engine, TEST_LOCK_KEY), PipelineTrigger.LOCAL)
        cleanup.append(out.run_id)
        assert out.status is PipelineStatus.LOCKED and steps.calls == []
        with engine.connect() as conn:
            row = conn.execute(select(PipelineRun).where(PipelineRun.id == out.run_id)).one()
        assert row.status == PipelineStatus.LOCKED and row.trigger == PipelineTrigger.LOCAL
        assert row.finished_at is not None and row.finished_at >= row.started_at
    finally:
        holder.unlock()

    # released: the next run gets the lock and records its outcome
    out = orchestrator.run(Steps(), DbRunLog(engine, TEST_LOCK_KEY), PipelineTrigger.LOCAL)
    cleanup.append(out.run_id)
    assert out.status is PipelineStatus.SKIPPED
    with engine.connect() as conn:
        row = conn.execute(select(PipelineRun).where(PipelineRun.id == out.run_id)).one()
        md = render(load_report(conn, out.run_id))
    assert row.status == PipelineStatus.SKIPPED and row.changed is False
    assert row.summary["watermark"] == "2026-11-04T00:00:00+00:00"
    assert f"## Matchday pipeline run {out.run_id}: `skipped`" in md


def test_failed_run_is_recorded(engine, cleanup):
    out = orchestrator.run(
        Steps(updated=1, fail_in="simulate"), DbRunLog(engine, TEST_LOCK_KEY),
        PipelineTrigger.MANUAL,
    )  # fmt: skip
    cleanup.append(out.run_id)
    with engine.connect() as conn:
        row = conn.execute(select(PipelineRun).where(PipelineRun.id == out.run_id)).one()
    assert row.status == PipelineStatus.FAILED and row.error == "RuntimeError('simulate broke')"
    assert row.model_run_ids == [21, 22] and row.simulation_run_id is None
    assert row.summary["step"] == "simulate"


def test_baseline_queries_run(engine):
    with engine.connect() as conn:
        n = changed_since_last_ok(conn)
    assert n is None or n >= 0
    assert DbSteps(engine, token="unused").watermark() is not None
