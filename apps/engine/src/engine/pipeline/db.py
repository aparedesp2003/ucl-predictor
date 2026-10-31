"""Database-backed pipeline steps and run log."""

import logging
from datetime import datetime

from sqlalchemy import Connection, Engine, func, insert, select, text, update

from engine.db.models import PipelineRun, PipelineStatus, PipelineTrigger, Source
from engine.ingest import football_data
from engine.ingest.load import LoadStats, build_resolver, finish_run, load_season, start_run
from engine.models.__main__ import predict_primary
from engine.pipeline.changes import IngestResult, diff_states, parsed_states, stored_states
from engine.pipeline.orchestrator import Outcome
from engine.simulate.__main__ import run_simulation

logger = logging.getLogger(__name__)

# pg_try_advisory_lock key shared by every pipeline run ("UCLP").
LOCK_KEY = 0x55434C50

# Matches are compared with the watermark (max matches.updated_at) stored by the last ok run; before
# the first one, with the latest simulation, the last step of a manual week-3 style run.
_BASELINE = text(
    """
    SELECT COALESCE(
        (SELECT (summary->>'watermark')::timestamptz FROM pipeline_runs
         WHERE status = 'ok' AND summary->>'watermark' IS NOT NULL
         ORDER BY id DESC LIMIT 1),
        (SELECT max(created_at) FROM simulation_runs)
    )
    """
)


def changed_since_last_ok(conn: Connection) -> int | None:
    baseline = conn.scalar(_BASELINE)
    if baseline is None:
        return None
    return conn.scalar(text("SELECT count(*) FROM matches WHERE updated_at > :b"), {"b": baseline})


class DbSteps:
    def __init__(self, engine: Engine, token: str) -> None:
        self.engine = engine
        self.token = token

    def ingest(self, dry_run: bool) -> IngestResult:
        season = football_data.parse(football_data.fetch(self.token, cache=not dry_run))
        with self.engine.connect() as conn:
            changes = diff_states(stored_states(conn), parsed_states(season))
        if dry_run:
            return IngestResult(None, 0, 0, changes)

        run_id = start_run(self.engine, Source.FOOTBALL_DATA)
        stats = LoadStats()
        try:
            with self.engine.begin() as conn:
                stats = load_season(conn, season, build_resolver(conn))
        except Exception as exc:
            finish_run(self.engine, run_id, stats, error=repr(exc))
            raise
        finish_run(self.engine, run_id, stats)
        unresolved = sorted(stats.unresolved)
        if unresolved:
            logger.warning("unresolved team names: %s", unresolved)
        return IngestResult(
            run_id, stats.matches_inserted, stats.matches_updated, changes, unresolved
        )

    def changed_since_last_ok(self) -> int | None:
        with self.engine.connect() as conn:
            return changed_since_last_ok(conn)

    def watermark(self) -> datetime | None:
        with self.engine.connect() as conn:
            return conn.scalar(text("SELECT max(updated_at) FROM matches"))

    def predict(self) -> list[int]:
        return list(predict_primary(self.engine).values())

    def simulate(self) -> int:
        sim_id, ok = run_simulation(self.engine)
        if not ok:
            raise RuntimeError(f"simulation invariants failed (simulation_runs id {sim_id})")
        return sim_id


class DbRunLog:
    """pipeline_runs rows, plus a session-level advisory lock held on a dedicated connection."""

    def __init__(self, engine: Engine, lock_key: int = LOCK_KEY) -> None:
        self.engine = engine
        self.lock_key = lock_key
        self._lock_conn: Connection | None = None

    def try_lock(self) -> bool:
        conn = self.engine.connect()
        got = conn.scalar(select(func.pg_try_advisory_lock(self.lock_key)))
        conn.commit()  # the lock is session-level; don't sit idle in a transaction
        if got:
            self._lock_conn = conn
        else:
            conn.close()
        return bool(got)

    def unlock(self) -> None:
        if self._lock_conn is None:
            return
        try:
            self._lock_conn.scalar(select(func.pg_advisory_unlock(self.lock_key)))
            self._lock_conn.commit()
        finally:
            self._lock_conn.close()
            self._lock_conn = None

    def start(self, trigger: PipelineTrigger) -> int:
        with self.engine.begin() as conn:
            return conn.scalar(
                insert(PipelineRun)
                .values(trigger=trigger, status=PipelineStatus.RUNNING)
                .returning(PipelineRun.id)
            )

    def record_locked(self, trigger: PipelineTrigger) -> int:
        with self.engine.begin() as conn:
            return conn.scalar(
                insert(PipelineRun)
                .values(trigger=trigger, status=PipelineStatus.LOCKED, finished_at=func.now())
                .returning(PipelineRun.id)
            )

    def finish(self, run_id: int, outcome: Outcome) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(PipelineRun)
                .where(PipelineRun.id == run_id)
                .values(
                    finished_at=func.now(),
                    status=outcome.status,
                    changed=outcome.changed,
                    ingest_run_id=outcome.ingest_run_id,
                    model_run_ids=outcome.model_run_ids or None,
                    simulation_run_id=outcome.simulation_run_id,
                    summary=outcome.summary,
                    error=outcome.error,
                )
            )
