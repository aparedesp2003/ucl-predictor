"""Idempotent loaders: upsert parsed seasons into Postgres (INSERT ... ON CONFLICT DO UPDATE)."""

import dataclasses
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Connection, Engine, func, literal_column, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from engine.db.models import (
    Competition,
    IngestRun,
    Match,
    RunStatus,
    Season,
    Source,
    Team,
    TeamAlias,
)
from engine.ingest.common import ParsedSeason, TeamRef
from engine.ingest.teams import TeamResolver, load_overrides

logger = logging.getLogger(__name__)

COMPETITION_CODE = "CL"
COMPETITION_NAME = "UEFA Champions League"

_MATCH_COLUMNS = (
    "season_id",
    "stage",
    "matchday",
    "leg",
    "match_date",
    "kickoff_utc",
    "home_team_id",
    "away_team_id",
    "status",
    "home_goals_90",
    "away_goals_90",
    "home_goals_et",
    "away_goals_et",
    "home_pens",
    "away_pens",
    "neutral_venue",
)


@dataclass
class LoadStats:
    matches_inserted: int = 0
    matches_updated: int = 0
    teams_inserted: int = 0
    teams_updated: int = 0
    aliases_inserted: int = 0
    matches_skipped: int = 0
    unresolved: Counter[str] = field(default_factory=Counter)
    resolved_by: Counter[str] = field(default_factory=Counter)

    def __iadd__(self, other: "LoadStats") -> "LoadStats":
        for f in dataclasses.fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))
        return self

    @property
    def rows_inserted(self) -> int:
        return self.matches_inserted + self.teams_inserted + self.aliases_inserted

    @property
    def rows_updated(self) -> int:
        return self.matches_updated + self.teams_updated


def build_resolver(conn: Connection) -> TeamResolver:
    resolver = TeamResolver(load_overrides())
    for tid, name, country in conn.execute(select(Team.id, Team.name, Team.country)):
        resolver.add_team(tid, name, country)
    for tid, source, alias in conn.execute(
        select(TeamAlias.team_id, TeamAlias.source, TeamAlias.alias)
    ):
        resolver.add_alias(tid, source, alias)
    return resolver


def _competition_id(conn: Connection) -> int:
    stmt = (
        insert(Competition)
        .values(code=COMPETITION_CODE, name=COMPETITION_NAME)
        .on_conflict_do_nothing(index_elements=["code"])
    )
    conn.execute(stmt)
    return conn.scalar(select(Competition.id).where(Competition.code == COMPETITION_CODE))


def _season_id(conn: Connection, season: ParsedSeason) -> int:
    values = {
        "competition_id": _competition_id(conn),
        "label": season.label,
        "start_date": season.start_date,
        "end_date": season.end_date,
        "format": season.format,
    }
    stmt = insert(Season).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["competition_id", "label"],
        set_={k: stmt.excluded[k] for k in ("start_date", "end_date", "format")},
    ).returning(Season.id)
    return conn.scalar(stmt)


def _add_alias(
    conn: Connection, resolver: TeamResolver, team_id: int, source: Source, alias: str
) -> int:
    if resolver.has_alias(source, alias):
        return 0
    stmt = (
        insert(TeamAlias)
        .values(team_id=team_id, source=source, alias=alias)
        .on_conflict_do_nothing(index_elements=["source", "alias"])
        .returning(TeamAlias.id)
    )
    inserted = len(conn.execute(stmt).all())
    resolver.add_alias(team_id, source, alias)
    return inserted


def _create_team(conn: Connection, resolver: TeamResolver, ref: TeamRef, name: str) -> int:
    tid = conn.scalar(
        insert(Team)
        .values(
            name=name,
            short_name=ref.short_name,
            tla=ref.tla,
            country=ref.country,
            fd_team_id=ref.fd_team_id,
            crest_url=ref.crest_url,
        )
        .returning(Team.id)
    )
    resolver.add_team(tid, name, ref.country)
    return tid


def _fd_team(conn: Connection, resolver: TeamResolver, ref: TeamRef, stats: LoadStats) -> int:
    """football-data teams are keyed by fd_team_id; a new id may attach to a known team."""
    tid = conn.scalar(select(Team.id).where(Team.fd_team_id == ref.fd_team_id))
    if tid is None:
        res = resolver.resolve(Source.FOOTBALL_DATA, ref.name, ref.country)
        if res.ambiguous:
            stats.unresolved[f"football_data: {ref.name} ({ref.country})"] += 1
        tid = res.team_id
    if tid is None:
        tid = _create_team(conn, resolver, ref, ref.name)
        stats.teams_inserted += 1
    else:
        # Refresh football-data attributes; the canonical name stays as first created.
        changed_if = [
            Team.fd_team_id.is_distinct_from(ref.fd_team_id),
            Team.short_name.is_distinct_from(ref.short_name),
            Team.tla.is_distinct_from(ref.tla),
            Team.crest_url.is_distinct_from(ref.crest_url),
        ]
        if ref.country is not None:
            changed_if.append(Team.country.is_(None))
        changed = conn.execute(
            update(Team)
            .where(Team.id == tid, or_(*changed_if))
            .values(
                fd_team_id=ref.fd_team_id,
                short_name=ref.short_name,
                tla=ref.tla,
                crest_url=ref.crest_url,
                country=func.coalesce(Team.country, ref.country),
            )
        ).rowcount
        stats.teams_updated += changed
    for alias in {ref.name, ref.short_name} - {None}:
        stats.aliases_inserted += _add_alias(conn, resolver, tid, Source.FOOTBALL_DATA, alias)
    return tid


def _openfootball_team(
    conn: Connection, resolver: TeamResolver, ref: TeamRef, stats: LoadStats
) -> int | None:
    res = resolver.resolve(Source.OPENFOOTBALL, ref.name, ref.country)
    tid = res.team_id
    if tid is None and res.ambiguous:
        stats.unresolved[f"openfootball: {ref.name} ({ref.country})"] += 1
        return None
    if tid is None:
        # Not in the current season: create from the openfootball name, or from an override
        # target that does not exist yet.
        target = resolver.override_target(Source.OPENFOOTBALL, ref.name) or ref.name
        tid = _create_team(conn, resolver, ref, target)
        stats.teams_inserted += 1
        stats.resolved_by["created"] += 1
    else:
        stats.resolved_by[res.how.value] += 1
    stats.aliases_inserted += _add_alias(conn, resolver, tid, Source.OPENFOOTBALL, ref.name)
    return tid


def load_season(conn: Connection, season: ParsedSeason, resolver: TeamResolver) -> LoadStats:
    """Upsert one season's teams and matches on ``conn`` (the caller owns the transaction)."""
    stats = LoadStats()
    season_id = _season_id(conn, season)
    team_ids: dict[TeamRef, int | None] = {}
    rows = []
    for m in season.matches:
        ids = []
        for ref in (m.home, m.away):
            if ref not in team_ids:
                if m.source is Source.FOOTBALL_DATA:
                    team_ids[ref] = _fd_team(conn, resolver, ref, stats)
                else:
                    team_ids[ref] = _openfootball_team(conn, resolver, ref, stats)
            ids.append(team_ids[ref])
        if None in ids:
            stats.matches_skipped += 1
            continue
        row = {c: getattr(m, c) for c in _MATCH_COLUMNS if hasattr(m, c)}
        row |= {
            "season_id": season_id,
            "source": m.source,
            "source_key": m.source_key,
            "home_team_id": ids[0],
            "away_team_id": ids[1],
        }
        rows.append(row)

    if rows:
        stmt = insert(Match).values(rows)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "source_key"],
            set_={**{c: excluded[c] for c in _MATCH_COLUMNS}, "updated_at": func.now()},
            where=or_(*(getattr(Match, c).is_distinct_from(excluded[c]) for c in _MATCH_COLUMNS)),
        ).returning(literal_column("xmax = 0").label("inserted"))
        for (inserted,) in conn.execute(stmt):
            if inserted:
                stats.matches_inserted += 1
            else:
                stats.matches_updated += 1
    return stats


def start_run(engine: Engine, source: Source) -> int:
    with engine.begin() as conn:
        return conn.scalar(
            insert(IngestRun)
            .values(source=source, status=RunStatus.RUNNING)
            .returning(IngestRun.id)
        )


def finish_run(engine: Engine, run_id: int, stats: LoadStats, error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(IngestRun)
            .where(IngestRun.id == run_id)
            .values(
                finished_at=datetime.now(UTC),
                status=RunStatus.FAILED if error else RunStatus.OK,
                rows_inserted=stats.rows_inserted,
                rows_updated=stats.rows_updated,
                error=error,
            )
        )
