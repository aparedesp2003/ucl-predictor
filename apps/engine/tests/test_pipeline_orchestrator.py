from datetime import UTC, datetime

import pytest

from engine.db.models import PipelineStatus, PipelineTrigger
from engine.pipeline import orchestrator
from engine.pipeline.changes import Changes, IngestResult


class FakeSteps:
    def __init__(self, updated=0, changed_since=0, fail_in=None) -> None:
        self.calls: list[str] = []
        self.updated = updated
        self.changed_since = changed_since
        self.fail_in = fail_in

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if name == self.fail_in:
            raise RuntimeError(f"{name} broke")

    def ingest(self, dry_run: bool) -> IngestResult:
        self._call("ingest:dry" if dry_run else "ingest")
        changes = Changes(newly_finished=["A v B 1-0 (MD4)"] if self.updated else [])
        return IngestResult(None if dry_run else 11, 0, self.updated, changes)

    def changed_since_last_ok(self) -> int | None:
        self._call("changed_since")
        return self.changed_since

    def watermark(self) -> datetime | None:
        self._call("watermark")
        return datetime(2026, 11, 4, tzinfo=UTC)

    def predict(self) -> list[int]:
        self._call("predict")
        return [21, 22]

    def simulate(self) -> int:
        self._call("simulate")
        return 31


class FakeLog:
    def __init__(self, locked: bool = False) -> None:
        self.locked = locked
        self.events: list[tuple] = []
        self.finished: dict[int, orchestrator.Outcome] = {}

    def try_lock(self) -> bool:
        self.events.append(("lock",))
        return not self.locked

    def unlock(self) -> None:
        self.events.append(("unlock",))

    def start(self, trigger: PipelineTrigger) -> int:
        self.events.append(("start", trigger))
        return 1

    def record_locked(self, trigger: PipelineTrigger) -> int:
        self.events.append(("locked", trigger))
        return 2

    def finish(self, run_id: int, outcome: orchestrator.Outcome) -> None:
        self.events.append(("finish", run_id, outcome.status))
        self.finished[run_id] = outcome


def test_changed_runs_steps_in_order():
    steps, log = FakeSteps(updated=1, changed_since=1), FakeLog()
    out = orchestrator.run(steps, log, PipelineTrigger.SCHEDULE)
    assert steps.calls == ["ingest", "changed_since", "watermark", "predict", "simulate"]
    assert log.events == [
        ("lock",), ("start", PipelineTrigger.SCHEDULE), ("finish", 1, PipelineStatus.OK),
        ("unlock",),
    ]  # fmt: skip
    assert out.status is PipelineStatus.OK and out.changed is True and out.exit_code == 0
    assert (out.ingest_run_id, out.model_run_ids, out.simulation_run_id) == (11, [21, 22], 31)
    assert out.summary["changes"]["newly_finished"] == ["A v B 1-0 (MD4)"]
    assert out.summary["watermark"] == "2026-11-04T00:00:00+00:00"
    assert set(out.summary["timings_s"]) == {"ingest", "predict", "simulate"}
    assert "step" not in out.summary


def test_quiet_day_is_skipped():
    steps, log = FakeSteps(), FakeLog()
    out = orchestrator.run(steps, log, PipelineTrigger.SCHEDULE)
    assert steps.calls == ["ingest", "changed_since", "watermark"]
    assert out.status is PipelineStatus.SKIPPED and out.changed is False and out.exit_code == 0
    assert log.finished[1] is out and out.model_run_ids == [] and out.simulation_run_id is None


def test_force_runs_on_a_quiet_day():
    steps = FakeSteps()
    out = orchestrator.run(steps, FakeLog(), PipelineTrigger.MANUAL, force=True)
    assert steps.calls[-2:] == ["predict", "simulate"]
    assert out.status is PipelineStatus.OK and out.changed is False
    assert out.summary["forced"] is True


def test_failure_in_predict_records_failed_and_skips_simulate():
    steps, log = FakeSteps(updated=1, fail_in="predict"), FakeLog()
    out = orchestrator.run(steps, log, PipelineTrigger.SCHEDULE)
    assert "simulate" not in steps.calls
    assert out.status is PipelineStatus.FAILED and out.exit_code == 1
    assert out.error == "RuntimeError('predict broke')"
    assert out.summary["step"] == "predict"
    assert out.ingest_run_id == 11 and out.simulation_run_id is None
    assert log.events[-2:] == [("finish", 1, PipelineStatus.FAILED), ("unlock",)]


def test_failure_in_ingest_records_failed():
    steps, log = FakeSteps(fail_in="ingest"), FakeLog()
    out = orchestrator.run(steps, log, PipelineTrigger.LOCAL)
    assert steps.calls == ["ingest"]
    assert out.status is PipelineStatus.FAILED and out.summary["step"] == "ingest"
    assert out.changed is None and log.events[-1] == ("unlock",)


def test_lock_held_records_locked_and_does_nothing():
    steps, log = FakeSteps(updated=1), FakeLog(locked=True)
    out = orchestrator.run(steps, log, PipelineTrigger.SCHEDULE)
    assert steps.calls == []
    assert log.events == [("lock",), ("locked", PipelineTrigger.SCHEDULE)]
    assert out.status is PipelineStatus.LOCKED and out.run_id == 2 and out.exit_code == 0


def test_unlocks_even_if_the_run_log_fails():
    class BrokenLog(FakeLog):
        def finish(self, run_id, outcome):
            raise ConnectionError("db gone")

    log = BrokenLog()
    with pytest.raises(ConnectionError):
        orchestrator.run(FakeSteps(), log, PipelineTrigger.LOCAL)
    assert log.events[-1] == ("unlock",)


@pytest.mark.parametrize(
    ("updated", "status"), [(0, PipelineStatus.SKIPPED), (1, PipelineStatus.OK)]
)
def test_dry_run_never_touches_the_log_or_writing_steps(updated, status):
    steps = FakeSteps(updated=updated)
    out = orchestrator.dry_run(steps)
    assert steps.calls == ["ingest:dry", "changed_since"]
    assert out.status is status and out.run_id is None
