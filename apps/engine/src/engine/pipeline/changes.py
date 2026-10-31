"""What a football-data ingest changes, and whether the pipeline should run.

The pipeline compares the parsed API payload with the stored football-data matches (keyed by
``source_key``) to say *what* changed, and relies on the loader's insert/update counts and on
``matches.updated_at`` to decide *whether* anything did.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime

from sqlalchemy import Connection, select

from engine.db.models import Match, MatchStatus, Source, Team
from engine.ingest.common import ParsedSeason

_GOALS = (
    "home_goals_90",
    "away_goals_90",
    "home_goals_et",
    "away_goals_et",
    "home_pens",
    "away_pens",
)


@dataclass(frozen=True)
class MatchState:
    """The columns of a football-data match that the loader upserts, minus team ids."""

    stage: str
    matchday: int | None
    leg: int | None
    match_date: date
    kickoff_utc: datetime | None
    status: str
    home_goals_90: int | None = None
    away_goals_90: int | None = None
    home_goals_et: int | None = None
    away_goals_et: int | None = None
    home_pens: int | None = None
    away_pens: int | None = None
    neutral_venue: bool = False
    label: str = field(default="", compare=False)  # "Home v Away", for reports only

    @property
    def score(self) -> str:
        return f"{self.home_goals_90}-{self.away_goals_90}"


@dataclass
class Changes:
    """Human-readable descriptions of each changed match, by kind."""

    new_fixtures: list[str] = field(default_factory=list)
    newly_finished: list[str] = field(default_factory=list)
    score_changed: list[str] = field(default_factory=list)
    status_changed: list[str] = field(default_factory=list)
    kickoff_changed: list[str] = field(default_factory=list)
    other_changed: list[str] = field(default_factory=list)

    def any(self) -> bool:
        return any(getattr(self, f.name) for f in fields(self))

    def counts(self) -> dict[str, int]:
        return {f.name: len(getattr(self, f.name)) for f in fields(self)}

    def to_dict(self) -> dict[str, list[str]]:
        return asdict(self)


def _md(s: MatchState) -> str:
    return f"{s.stage} MD{s.matchday}" if s.matchday is not None else s.stage


def _ko(s: MatchState) -> str:
    return f"{s.kickoff_utc:%Y-%m-%d %H:%M}Z" if s.kickoff_utc else f"{s.match_date} (no time)"


def diff_states(before: Mapping[str, MatchState], after: Mapping[str, MatchState]) -> Changes:
    """Classify matches in ``after`` that are new or differ from ``before``.

    A match is listed once per kind that applies (a rescheduled match that also changed status
    appears under both). Matches missing from ``after`` are ignored: the loader never deletes.
    """
    out = Changes()
    for key, new in after.items():
        old = before.get(key)
        if old is None:
            out.new_fixtures.append(f"{new.label} ({_md(new)}, {_ko(new)})")
            continue
        if old == new:
            continue
        finished = MatchStatus.FINISHED.value
        known = False
        if new.status == finished and old.status != finished:
            out.newly_finished.append(f"{new.label} {new.score} ({_md(new)})")
            known = True
        elif new.status != old.status:
            out.status_changed.append(f"{new.label}: {old.status} -> {new.status}")
            known = True
        elif new.status == finished and any(getattr(old, g) != getattr(new, g) for g in _GOALS):
            out.score_changed.append(f"{new.label}: {old.score} -> {new.score}")
            known = True
        if (old.kickoff_utc, old.match_date) != (new.kickoff_utc, new.match_date):
            out.kickoff_changed.append(f"{new.label}: {_ko(old)} -> {_ko(new)}")
            known = True
        if not known:
            diffs = [
                f.name
                for f in fields(MatchState)
                if f.compare and getattr(old, f.name) != getattr(new, f.name)
            ]
            out.other_changed.append(f"{new.label}: {', '.join(diffs)}")
    return out


def parsed_states(season: ParsedSeason) -> dict[str, MatchState]:
    return {
        m.source_key: MatchState(
            stage=m.stage.value,
            matchday=m.matchday,
            leg=m.leg,
            match_date=m.match_date,
            kickoff_utc=m.kickoff_utc,
            status=m.status.value,
            home_goals_90=m.home_goals_90,
            away_goals_90=m.away_goals_90,
            home_goals_et=m.home_goals_et,
            away_goals_et=m.away_goals_et,
            home_pens=m.home_pens,
            away_pens=m.away_pens,
            neutral_venue=m.neutral_venue,
            label=f"{m.home.name} v {m.away.name}",
        )
        for m in season.matches
        if m.source is Source.FOOTBALL_DATA
    }


def stored_states(conn: Connection) -> dict[str, MatchState]:
    """The football-data matches currently in the database."""
    home, away = Team.__table__.alias("h"), Team.__table__.alias("a")
    rows = conn.execute(
        select(Match.__table__, home.c.name.label("home_name"), away.c.name.label("away_name"))
        .join(home, home.c.id == Match.home_team_id)
        .join(away, away.c.id == Match.away_team_id)
        .where(Match.source == Source.FOOTBALL_DATA)
    ).all()
    compared = [f.name for f in fields(MatchState) if f.compare]
    return {
        r.source_key: MatchState(
            **{c: getattr(r, c) for c in compared}, label=f"{r.home_name} v {r.away_name}"
        )
        for r in rows
    }


@dataclass(frozen=True)
class IngestResult:
    run_id: int | None  # None on a dry run
    matches_inserted: int
    matches_updated: int
    changes: Changes
    unresolved: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    changed: bool
    run: bool
    reason: str


def decide(ingest: IngestResult, changed_since_last_ok: int | None, force: bool) -> Decision:
    """Run predict + simulate when the ingest touched any match, when matches were updated since
    the last ok pipeline run (``None``: there is no baseline yet), or when forced."""
    reasons = []
    if ingest.matches_inserted or ingest.matches_updated:
        reasons.append(
            f"ingest inserted {ingest.matches_inserted} / updated {ingest.matches_updated} matches"
        )
    elif ingest.changes.any():  # dry run: no counts, the diff predicts them
        reasons.append(f"ingest would change {ingest.changes.counts()}")
    if changed_since_last_ok is None:
        reasons.append("no earlier pipeline or simulation run to compare with")
    elif changed_since_last_ok:
        reasons.append(f"{changed_since_last_ok} matches updated since the last ok run")
    changed = bool(reasons)
    if force:
        reasons.append("--force")
    return Decision(changed, bool(reasons), "; ".join(reasons) or "nothing changed")
