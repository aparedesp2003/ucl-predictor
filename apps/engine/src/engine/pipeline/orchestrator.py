"""Matchday pipeline: ingest -> decide -> predict -> simulate, recorded in ``pipeline_runs``.

The steps and the run log are protocols so the control flow can be tested without a database.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from engine.db.models import PipelineStatus, PipelineTrigger
from engine.pipeline.changes import Decision, IngestResult, decide

logger = logging.getLogger(__name__)


class Steps(Protocol):
    def ingest(self, dry_run: bool) -> IngestResult: ...

    def changed_since_last_ok(self) -> int | None:
        """Matches updated after the last ok run's watermark (None: no baseline exists)."""
        ...

    def watermark(self) -> datetime | None:
        """Latest ``matches.updated_at``; stored so the next run can compare against it."""
        ...

    def predict(self) -> list[int]: ...

    def simulate(self) -> int: ...


class RunLog(Protocol):
    def try_lock(self) -> bool: ...

    def unlock(self) -> None: ...

    def start(self, trigger: PipelineTrigger) -> int: ...

    def record_locked(self, trigger: PipelineTrigger) -> int: ...

    def finish(self, run_id: int, outcome: "Outcome") -> None: ...


@dataclass
class Outcome:
    status: PipelineStatus
    run_id: int | None = None
    changed: bool | None = None
    decision: Decision | None = None
    ingest_run_id: int | None = None
    model_run_ids: list[int] = field(default_factory=list)
    simulation_run_id: int | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def exit_code(self) -> int:
        return 1 if self.status is PipelineStatus.FAILED else 0


def _timed[T](outcome: Outcome, step: str, fn: Callable[[], T]) -> T:
    start = time.perf_counter()
    try:
        return fn()
    finally:
        outcome.summary.setdefault("timings_s", {})[step] = round(time.perf_counter() - start, 2)


def _ingest_summary(ingest: IngestResult, changed_since: int | None, decision: Decision) -> dict:
    return {
        "ingest": {
            "matches_inserted": ingest.matches_inserted,
            "matches_updated": ingest.matches_updated,
            "unresolved": ingest.unresolved,
        },
        "changes": ingest.changes.to_dict(),
        "changed_since_last_ok": changed_since,
        "decision": decision.reason,
    }


def dry_run(steps: Steps, force: bool = False) -> Outcome:
    """Fetch and diff against the database without writing anything."""
    outcome = Outcome(PipelineStatus.RUNNING)
    ingest = _timed(outcome, "ingest", lambda: steps.ingest(dry_run=True))
    changed_since = steps.changed_since_last_ok()
    decision = decide(ingest, changed_since, force)
    outcome.changed, outcome.decision = decision.changed, decision
    outcome.summary |= _ingest_summary(ingest, changed_since, decision)
    outcome.status = PipelineStatus.OK if decision.run else PipelineStatus.SKIPPED
    return outcome


def run(steps: Steps, log: RunLog, trigger: PipelineTrigger, force: bool = False) -> Outcome:
    if not log.try_lock():
        run_id = log.record_locked(trigger)
        logger.warning("another pipeline run holds the lock; recorded pipeline_runs %s", run_id)
        return Outcome(PipelineStatus.LOCKED, run_id=run_id)
    try:
        outcome = Outcome(PipelineStatus.RUNNING, run_id=log.start(trigger))
        outcome.summary["forced"] = force
        try:
            _run_steps(steps, outcome, force)
        except Exception as exc:
            logger.exception("pipeline step failed")
            outcome.status, outcome.error = PipelineStatus.FAILED, repr(exc)
        log.finish(outcome.run_id, outcome)
        return outcome
    finally:
        log.unlock()


def _run_steps(steps: Steps, outcome: Outcome, force: bool) -> None:
    outcome.summary["step"] = "ingest"
    ingest = _timed(outcome, "ingest", lambda: steps.ingest(dry_run=False))
    outcome.ingest_run_id = ingest.run_id

    outcome.summary["step"] = "decide"
    changed_since = steps.changed_since_last_ok()
    decision = decide(ingest, changed_since, force)
    outcome.changed, outcome.decision = decision.changed, decision
    outcome.summary |= _ingest_summary(ingest, changed_since, decision)
    watermark = steps.watermark()
    outcome.summary["watermark"] = watermark.isoformat() if watermark else None
    if not decision.run:
        outcome.summary.pop("step")
        outcome.status = PipelineStatus.SKIPPED
        return

    outcome.summary["step"] = "predict"
    outcome.model_run_ids = _timed(outcome, "predict", steps.predict)
    outcome.summary["step"] = "simulate"
    outcome.simulation_run_id = _timed(outcome, "simulate", steps.simulate)
    outcome.summary.pop("step")
    outcome.status = PipelineStatus.OK
