from datetime import UTC, date, datetime

import pytest

from engine.db.models import MatchStatus, Source, Stage
from engine.ingest.openfootball import parse_score, parse_season, parse_stage, parse_text


@pytest.fixture
def matches(cl_sample):
    season = parse_season("2011-12", [cl_sample])
    return {(m.home.name, m.away.name, m.stage): m for m in season.matches}


def test_regular_result_and_kickoff_in_utc(matches):
    m = matches[("Manchester City", "SSC Napoli", Stage.GROUP_STAGE)]
    assert m.source is Source.OPENFOOTBALL
    assert (m.home_goals_90, m.away_goals_90) == (1, 1)
    assert m.home.country == "ENG" and m.away.country == "ITA"
    assert m.match_date == date(2011, 9, 14)
    assert m.kickoff_utc == datetime(2011, 9, 14, 18, 45, tzinfo=UTC)  # 20:45 CEST
    assert m.status is MatchStatus.FINISHED
    assert m.source_key == "2011-12|GROUP_STAGE|2011-09-14|Manchester City|SSC Napoli"


def test_year_inferred_and_winter_time(matches):
    m = matches[("SSC Napoli", "Manchester City", Stage.GROUP_STAGE)]
    assert m.match_date == date(2011, 11, 22)
    assert m.kickoff_utc == datetime(2011, 11, 22, 19, 45, tzinfo=UTC)  # 20:45 CET


def test_extra_time_keeps_90_minute_score(matches):
    m = matches[("Chelsea FC", "SSC Napoli", Stage.LAST_16)]
    assert (m.home_goals_90, m.away_goals_90) == (3, 1)
    assert (m.home_goals_et, m.away_goals_et) == (4, 1)
    assert m.home_pens is None


def test_penalties_final(matches):
    m = matches[("Bayern München", "Chelsea FC", Stage.FINAL)]
    assert m.match_date == date(2012, 5, 19)
    assert (m.home_goals_90, m.away_goals_90) == (1, 1)
    assert (m.home_goals_et, m.away_goals_et) == (1, 1)
    assert (m.home_pens, m.away_pens) == (3, 4)
    assert m.neutral_venue and m.leg is None


def test_time_carries_over_to_continuation_lines(matches):
    m = matches[("Real Madrid", "CSKA Moskva", Stage.LAST_16)]
    assert m.kickoff_utc == datetime(2012, 3, 14, 19, 45, tzinfo=UTC)


def test_legs_only_in_two_legged_stages(matches):
    group = [m for (_, _, stage), m in matches.items() if stage is Stage.GROUP_STAGE]
    assert len(group) == 2 and all(m.leg is None for m in group)  # same pair twice, not legs
    assert matches[("SSC Napoli", "Chelsea FC", Stage.LAST_16)].leg == 1
    assert matches[("Chelsea FC", "SSC Napoli", Stage.LAST_16)].leg == 2
    assert matches[("Real Madrid", "CSKA Moskva", Stage.LAST_16)].leg is None  # other leg trimmed


def test_explicit_year_carries_forward():
    text = (
        "▪ Quarterfinals\n  Wed Aug 12 2020\n"
        "    21:00  Atalanta (ITA)          v Paris Saint-Germain (FRA)  1-2 (1-0)\n"
        "  Thu Aug 13\n"
        "    21:00  RB Leipzig (GER)        v Atletico Madrid (ESP)    2-1 (0-0)\n"
    )
    a, b = parse_text("2019-20", text)
    assert (a.match_date, b.match_date) == (date(2020, 8, 12), date(2020, 8, 13))
    assert a.neutral_venue and b.neutral_venue


@pytest.mark.parametrize(
    ("text", "ft", "et", "pens"),
    [
        ("2-0", (2, 0), None, None),
        ("1-1 (0-1)", (1, 1), None, None),
        ("3-2 a.e.t. (3-0, 1-0)", (3, 0), (3, 2), None),
        ("4-3 pen. 1-1 a.e.t. (1-1, 0-1)", (1, 1), (1, 1), (4, 3)),
        ("8-7 pen. 0-0 a.e.t. (0-0)", (0, 0), (0, 0), (8, 7)),
    ],
)
def test_parse_score(text, ft, et, pens):
    s = parse_score(text)
    assert (s.ft, s.et, s.pens) == (ft, et, pens)


def test_parse_score_unplayed_and_garbage():
    assert parse_score("") is None
    with pytest.raises(ValueError):
        parse_score("3-3 abd.")


@pytest.mark.parametrize(
    ("heading", "qualifying", "stage", "matchday"),
    [
        ("Group C", False, Stage.GROUP_STAGE, None),
        ("Gruppe G", False, Stage.GROUP_STAGE, None),
        ("Group, Matchday 3", False, Stage.GROUP_STAGE, 3),
        ("League, Matchday 8", False, Stage.LEAGUE_PHASE, 8),
        ("Playoffs, Matchday 2", False, Stage.KNOCKOUT_PLAYOFF, None),
        ("Finals, Round of 16", False, Stage.LAST_16, None),
        ("Quarterfinals", False, Stage.QUARTER_FINALS, None),
        ("Finals, Final", False, Stage.FINAL, None),
        ("Round 2", True, Stage.QUALIFYING, None),
        ("3. Round", True, Stage.QUALIFYING, None),
        ("Play-offs", True, Stage.PLAYOFF_ROUND, None),
        ("Playoffs", True, Stage.PLAYOFF_ROUND, None),
    ],
)
def test_parse_stage(heading, qualifying, stage, matchday):
    assert parse_stage(heading, qualifying_file=qualifying) == (stage, matchday)


def test_unknown_heading_raises():
    with pytest.raises(ValueError):
        parse_stage("Intertoto Cup", qualifying_file=False)
