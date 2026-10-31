from dataclasses import replace
from datetime import UTC, date, datetime

from engine.db.models import MatchStatus, Source, Stage
from engine.ingest.common import ParsedMatch, ParsedSeason, TeamRef
from engine.pipeline.changes import (
    Changes,
    IngestResult,
    MatchState,
    decide,
    diff_states,
    parsed_states,
)

KO = datetime(2026, 11, 3, 17, 45, tzinfo=UTC)


def _state(**kw) -> MatchState:
    base = dict(
        stage="LEAGUE_PHASE", matchday=4, leg=None, match_date=KO.date(), kickoff_utc=KO,
        status="SCHEDULED", label="Arsenal v Bayern",
    )  # fmt: skip
    return MatchState(**(base | kw))


def _finished(h: int, a: int, **kw) -> MatchState:
    return _state(status="FINISHED", home_goals_90=h, away_goals_90=a, **kw)


BEFORE = {"1": _state(), "2": _state(label="Inter v Ajax")}


def test_identical_payload_has_no_changes():
    changes = diff_states(BEFORE, dict(BEFORE))
    assert not changes.any()
    assert changes.counts() == dict.fromkeys(changes.counts(), 0)


def test_label_is_not_compared():
    assert not diff_states(BEFORE, {"1": replace(BEFORE["1"], label="renamed")}).any()


def test_newly_finished():
    changes = diff_states(BEFORE, {**BEFORE, "1": _finished(2, 1)})
    assert changes.newly_finished == ["Arsenal v Bayern 2-1 (LEAGUE_PHASE MD4)"]
    assert changes.counts()["newly_finished"] == 1 and sum(changes.counts().values()) == 1


def test_kickoff_moved():
    later = datetime(2026, 11, 3, 20, 0, tzinfo=UTC)
    changes = diff_states(BEFORE, {**BEFORE, "1": _state(kickoff_utc=later)})
    assert changes.kickoff_changed == ["Arsenal v Bayern: 2026-11-03 17:45Z -> 2026-11-03 20:00Z"]
    assert sum(changes.counts().values()) == 1


def test_new_fixture_score_correction_status_and_other():
    before = {"1": _finished(1, 1), "2": _state(), "3": _state()}
    after = {
        "1": _finished(1, 2),  # score corrected
        "2": _state(status="POSTPONED"),
        "3": _state(matchday=5),
        "4": _state(label="Real v PSG", stage="KNOCKOUT_PLAYOFF", matchday=None),
    }
    changes = diff_states(before, after)
    assert changes.score_changed == ["Arsenal v Bayern: 1-1 -> 1-2"]
    assert changes.status_changed == ["Arsenal v Bayern: SCHEDULED -> POSTPONED"]
    assert changes.other_changed == ["Arsenal v Bayern: matchday"]
    assert changes.new_fixtures == ["Real v PSG (KNOCKOUT_PLAYOFF, 2026-11-03 17:45Z)"]
    assert not changes.newly_finished and not changes.kickoff_changed


def test_matches_missing_from_payload_are_ignored():
    assert not diff_states(BEFORE, {"1": BEFORE["1"]}).any()


def test_parsed_states_match_stored_shape():
    ref = TeamRef(name="Arsenal", country="ENG", fd_team_id=57)
    ref_b = TeamRef(name="Bayern", country="GER", fd_team_id=5)
    m = ParsedMatch(
        source=Source.FOOTBALL_DATA, source_key="1", season="2026-27", stage=Stage.LEAGUE_PHASE,
        match_date=date(2026, 11, 3), kickoff_utc=KO, home=ref, away=ref_b,
        status=MatchStatus.SCHEDULED, matchday=4,
    )  # fmt: skip
    states = parsed_states(ParsedSeason("2026-27", None, None, [m]))
    assert states == {"1": BEFORE["1"]}
    assert states["1"].label == "Arsenal v Bayern"


# --- decide: fake ingest results -----------------------------------------------------------------


def _ingest(inserted=0, updated=0, changes=None) -> IngestResult:
    return IngestResult(run_id=7, matches_inserted=inserted, matches_updated=updated,
                        changes=changes or Changes())  # fmt: skip


def test_nothing_changed_skips():
    d = decide(_ingest(), changed_since_last_ok=0, force=False)
    assert (d.changed, d.run, d.reason) == (False, False, "nothing changed")


def test_one_match_finished_runs():
    changes = diff_states(BEFORE, {**BEFORE, "1": _finished(0, 0)})
    d = decide(_ingest(updated=1, changes=changes), changed_since_last_ok=1, force=False)
    assert d.changed and d.run
    assert "updated 1" in d.reason


def test_kickoff_moved_runs():
    moved = {**BEFORE, "2": _state(label="Inter v Ajax", kickoff_utc=KO.replace(hour=20))}
    d = decide(_ingest(updated=1, changes=diff_states(BEFORE, moved)), 1, force=False)
    assert d.changed and d.run


def test_dry_run_diff_alone_triggers():
    changes = diff_states(BEFORE, {**BEFORE, "1": _finished(3, 0)})
    d = decide(_ingest(changes=changes), changed_since_last_ok=0, force=False)
    assert d.run and "would change" in d.reason


def test_updates_since_last_ok_run_trigger_even_if_this_ingest_was_quiet():
    # e.g. the previous run ingested a result, then failed in predict
    d = decide(_ingest(), changed_since_last_ok=3, force=False)
    assert d.changed and d.run and "3 matches updated" in d.reason


def test_no_baseline_runs():
    d = decide(_ingest(), changed_since_last_ok=None, force=False)
    assert d.changed and d.run


def test_force_runs_but_records_unchanged():
    d = decide(_ingest(), changed_since_last_ok=0, force=True)
    assert (d.changed, d.run, d.reason) == (False, True, "--force")
