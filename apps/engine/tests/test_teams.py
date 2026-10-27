import pytest

from engine.db.models import Source
from engine.ingest.football_data import COUNTRY_CODE_MAP
from engine.ingest.teams import How, Override, TeamResolver, normalize

OF, FD = Source.OPENFOOTBALL, Source.FOOTBALL_DATA


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Paris Saint-Germain FC", "Paris Saint-Germain"),
        ("Atlético Madrid", "Atletico Madrid"),
        ("FC Bayern München", "Bayern Munchen"),
        ("ŠK Slovan Bratislava", "Slovan Bratislava"),
        ("FK Bodø/Glimt", "FK Bodo Glimt"),
        ("AFC Ajax", "Ajax"),
        ("Fenerbahçe SK", "Fenerbahce"),
    ],
)
def test_normalize_equivalent(a, b):
    assert normalize(a) == normalize(b)


def test_normalize_output():
    assert normalize("FC Internazionale Milano") == "internazionale milano"
    assert normalize("Club Atlético de Madrid") == "club atletico de madrid"


@pytest.fixture
def resolver():
    r = TeamResolver()
    r.add_team(1, "FC Internazionale Milano", "ITA")
    r.add_alias(1, FD, "FC Internazionale Milano")
    r.add_alias(1, FD, "Inter")  # football-data shortName
    r.add_team(2, "Paris Saint-Germain FC", "FRA")
    r.add_alias(2, FD, "Paris Saint-Germain FC")
    r.add_team(3, "Club Atlético de Madrid", "ESP")
    return r


def test_exact_alias(resolver):
    assert resolver.resolve(FD, "Inter").how is How.ALIAS


def test_inter_resolves_via_short_name_alias(resolver):
    res = resolver.resolve(OF, "Inter", "ITA")
    assert (res.team_id, res.how) == (1, How.NORMALIZED)


def test_psg_normalized(resolver):
    assert resolver.resolve(OF, "Paris Saint-Germain", "FRA").team_id == 2


def test_accents_normalized(resolver):
    assert resolver.resolve(OF, "Club Atletico de Madrid", "ESP").team_id == 3


def test_short_spanish_name_needs_override(resolver):
    assert resolver.resolve(OF, "Atlético Madrid", "ESP").team_id is None
    r = TeamResolver([Override(OF, "Atlético Madrid", "Club Atlético de Madrid", "")])
    r.add_team(3, "Club Atlético de Madrid", "ESP")
    res = r.resolve(OF, "Atlético Madrid", "ESP")
    assert (res.team_id, res.how) == (3, How.OVERRIDE)


def test_country_guard_blocks_same_name_other_country():
    r = TeamResolver()
    r.add_team(10, "FC Barcelona", "ESP")
    assert normalize("Barcelona SC") == normalize("FC Barcelona") == "barcelona"
    res = r.resolve(OF, "Barcelona SC", "ECU")
    assert res.team_id is None and not res.ambiguous
    assert r.resolve(OF, "Barcelona", "ESP").team_id == 10
    assert r.resolve(OF, "Barcelona", None).team_id == 10  # unknown country: no guard


def test_country_guard_maps_code_schemes():
    r = TeamResolver()
    r.add_team(20, "FC Bayern München", COUNTRY_CODE_MAP["DEU"])  # stored as openfootball code
    assert r.resolve(OF, "Bayern München", "GER").team_id == 20


def test_override_bypasses_country_guard():
    r = TeamResolver([Override(OF, "AS Monaco FC", "AS Monaco", "FRA -> MCO")])
    r.add_team(30, "AS Monaco", "FRA")
    assert r.resolve(OF, "AS Monaco FC", "MCO").team_id == 30


def test_ambiguous_is_not_guessed():
    r = TeamResolver()
    r.add_team(40, "Dinamo", "ROU")
    r.add_team(41, "FC Dinamo", "ROU")
    res = r.resolve(OF, "Dinamo", "ROU")
    assert res.team_id is None and res.ambiguous


def test_possible_duplicates():
    r = TeamResolver()
    r.add_team(1, "PSV", "NED")
    r.add_team(2, "PSV Eindhoven", "NED")
    r.add_team(3, "AFC Ajax", "NED")
    r.add_team(4, "PSV", "ECU")
    assert r.possible_duplicates() == [("NED", "PSV", "PSV Eindhoven")]
