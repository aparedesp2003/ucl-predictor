from datetime import UTC, date, datetime

import pytest

from engine.models.store import PostKickoffUpdateError, kickoff_of, plan_prediction_writes

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)
PAST = datetime(2026, 11, 3, 20, tzinfo=UTC)
FUTURE = datetime(2026, 11, 5, 20, tzinfo=UTC)
OLD = (0.5, 0.3, 0.2)
NEW = (0.4, 0.3, 0.3)


def test_refuses_to_overwrite_post_kickoff_prediction():
    with pytest.raises(PostKickoffUpdateError):
        plan_prediction_writes({1: OLD}, {1: NEW}, {1: PAST}, NOW)
    with pytest.raises(PostKickoffUpdateError):
        plan_prediction_writes({1: OLD}, {1: NEW}, {1: NOW}, NOW)  # kick-off is inclusive


def test_identical_post_kickoff_prediction_is_left_alone():
    plan = plan_prediction_writes({1: OLD}, {1: OLD}, {1: PAST}, NOW)
    assert plan.unchanged == [1] and not plan.upserts


def test_pre_kickoff_updates_and_inserts_are_allowed():
    plan = plan_prediction_writes({1: OLD}, {1: NEW, 2: NEW}, {1: FUTURE, 2: FUTURE}, NOW)
    assert plan.upserts == {1: NEW, 2: NEW}


def test_new_prediction_for_started_match_is_skipped():
    plan = plan_prediction_writes({}, {1: NEW, 2: NEW}, {1: PAST, 2: FUTURE}, NOW)
    assert plan.skipped_started == [1]
    assert plan.upserts == {2: NEW}


def test_missing_kickoff_falls_back_to_midnight_utc():
    assert kickoff_of(None, date(2026, 11, 4)) == datetime(2026, 11, 4, tzinfo=UTC)
    assert kickoff_of(FUTURE, date(2026, 11, 4)) == FUTURE
