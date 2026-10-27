from datetime import UTC, datetime

import pytest

from engine.db.models import MatchStatus, SeasonFormat, Source, Stage
from engine.ingest.football_data import parse, scores


@pytest.fixture
def season(football_data_payload):
    return parse(football_data_payload)


@pytest.fixture
def by_key(season):
    return {m.source_key: m for m in season.matches}


def test_season_metadata(season):
    assert season.label == "2024-25"
    assert season.format is SeasonFormat.LEAGUE_PHASE
    assert str(season.start_date) == "2024-09-17"


def test_tbd_slots_are_skipped(by_key):
    assert "900007" not in by_key
    assert len(by_key) == 6


def test_regular_result(by_key):
    m = by_key["900001"]
    assert m.source is Source.FOOTBALL_DATA
    assert m.stage is Stage.LEAGUE_PHASE and m.matchday == 1 and m.leg is None
    assert (m.home_goals_90, m.away_goals_90) == (2, 3)
    assert m.home_goals_et is None and m.home_pens is None
    assert m.kickoff_utc == datetime(2024, 9, 17, 19, tzinfo=UTC)
    assert m.home.country == "BEL" and m.away.country == "GER"  # DEU mapped to openfootball code


def test_extra_time_uses_regular_time_for_90(by_key):
    m = by_key["900003"]
    assert m.stage is Stage.KNOCKOUT_PLAYOFF
    assert (m.home_goals_90, m.away_goals_90) == (3, 0)
    assert (m.home_goals_et, m.away_goals_et) == (3, 2)
    assert m.home_pens is None


def test_penalty_shootout_excludes_pens_from_90(by_key):
    m = by_key["900005"]
    assert (m.home_goals_90, m.away_goals_90) == (1, 0)
    assert (m.home_goals_et, m.away_goals_et) == (1, 0)
    assert (m.home_pens, m.away_pens) == (2, 4)


def test_legs_and_neutral_final(by_key):
    assert (by_key["900002"].leg, by_key["900003"].leg) == (1, 2)
    assert (by_key["900004"].leg, by_key["900005"].leg) == (1, 2)
    final = by_key["900006"]
    assert final.leg is None and final.neutral_venue
    assert final.status is MatchStatus.SCHEDULED and final.home_goals_90 is None


def test_scores_regular_uses_full_time():
    assert scores({"duration": "REGULAR", "fullTime": {"home": 1, "away": 0}}) == {
        "home_goals_90": 1,
        "away_goals_90": 0,
    }
