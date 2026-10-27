"""Runs the loaders against the real database inside a transaction that is rolled back."""

import os

import pytest

from engine.ingest import football_data, openfootball
from engine.ingest.load import build_resolver, load_season

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1"),
]


@pytest.fixture
def conn():
    from engine.db import get_engine

    with get_engine().connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()


def test_loaders_are_idempotent(conn, football_data_payload, cl_sample):
    # A label outside the real range keeps openfootball source keys from colliding with real rows.
    seasons = [
        football_data.parse(football_data_payload),
        openfootball.parse_season("1999-00", [cl_sample]),
    ]
    resolver = build_resolver(conn)
    for season in seasons:
        first = load_season(conn, season, resolver)
        assert first.matches_inserted == len(season.matches)
        assert not first.unresolved

    resolver = build_resolver(conn)
    for season in seasons:
        again = load_season(conn, season, resolver)
        assert (again.matches_inserted, again.matches_updated) == (0, 0)
        assert (again.teams_inserted, again.aliases_inserted) == (0, 0)
