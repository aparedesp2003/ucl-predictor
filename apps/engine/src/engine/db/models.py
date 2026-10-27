"""SQLAlchemy 2.0 models for the UCL schema. Alembic (migrations/) owns the DDL."""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SeasonFormat(StrEnum):
    GROUP_STAGE = "group_stage"
    LEAGUE_PHASE = "league_phase"


class Source(StrEnum):
    FOOTBALL_DATA = "football_data"
    OPENFOOTBALL = "openfootball"
    MANUAL = "manual"


class Stage(StrEnum):
    QUALIFYING = "QUALIFYING"
    PLAYOFF_ROUND = "PLAYOFF_ROUND"
    GROUP_STAGE = "GROUP_STAGE"
    LEAGUE_PHASE = "LEAGUE_PHASE"
    KNOCKOUT_PLAYOFF = "KNOCKOUT_PLAYOFF"
    LAST_16 = "LAST_16"
    QUARTER_FINALS = "QUARTER_FINALS"
    SEMI_FINALS = "SEMI_FINALS"
    FINAL = "FINAL"


class MatchStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"


class RunStatus(StrEnum):
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"


def _enum(cls: type[StrEnum], name: str) -> Enum:
    # varchar + CHECK instead of a native PG enum, so values can change with a plain migration.
    return Enum(
        cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(128))


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("competition_id", "label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"))
    label: Mapped[str] = mapped_column(String(7))  # "2024-25"
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    format: Mapped[SeasonFormat] = mapped_column(_enum(SeasonFormat, "season_format"))


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    short_name: Mapped[str | None] = mapped_column(String(64))
    tla: Mapped[str | None] = mapped_column(String(8))
    country: Mapped[str | None] = mapped_column(String(8))  # openfootball code scheme, e.g. GER
    fd_team_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    crest_url: Mapped[str | None] = mapped_column(Text)


class TeamAlias(Base):
    __tablename__ = "team_aliases"
    __table_args__ = (UniqueConstraint("source", "alias"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    source: Mapped[Source] = mapped_column(_enum(Source, "alias_source"))
    alias: Mapped[str] = mapped_column(String(128))


class Match(Base):
    """One UCL match from one source.

    Goal columns follow the 90-minute rule, because models train on regulation-time results:

    - ``home/away_goals_90``: score after 90 minutes (plus stoppage), never including extra time
      or penalties.
      * football-data v4: ``score.fullTime`` includes extra time (and, for shootouts, the
        penalties), so when ``score.duration != "REGULAR"`` we use ``score.regularTime``;
        otherwise ``score.fullTime``.
      * openfootball Football.TXT: the bracketed full-time score in ``E a.e.t. (F, H)`` /
        ``P pen. E a.e.t. (F, H)`` is the 90-minute score; for a plain ``F (H)`` it is ``F``.
    - ``home/away_goals_et``: cumulative score after extra time (90 + ET); NULL if no extra time.
      football-data: ``regularTime + extraTime``; Football.TXT: ``E`` in ``E a.e.t.``.
    - ``home/away_pens``: shootout score only; NULL if no shootout.
      football-data: ``score.penalties``; Football.TXT: ``P`` in ``P pen.``.

    ``match_date`` is the local match date from the source; ``kickoff_utc`` is NULL when the source
    has no kick-off time.
    """

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("source", "source_key"),
        Index("ix_matches_season_kickoff", "season_id", "kickoff_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    source: Mapped[Source] = mapped_column(_enum(Source, "match_source"))
    source_key: Mapped[str] = mapped_column(String(255))
    stage: Mapped[Stage] = mapped_column(_enum(Stage, "match_stage"))
    matchday: Mapped[int | None] = mapped_column(SmallInteger)
    leg: Mapped[int | None] = mapped_column(SmallInteger)
    match_date: Mapped[date] = mapped_column(Date)
    kickoff_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    status: Mapped[MatchStatus] = mapped_column(_enum(MatchStatus, "match_status"))
    home_goals_90: Mapped[int | None] = mapped_column(SmallInteger)
    away_goals_90: Mapped[int | None] = mapped_column(SmallInteger)
    home_goals_et: Mapped[int | None] = mapped_column(SmallInteger)
    away_goals_et: Mapped[int | None] = mapped_column(SmallInteger)
    home_pens: Mapped[int | None] = mapped_column(SmallInteger)
    away_pens: Mapped[int | None] = mapped_column(SmallInteger)
    neutral_venue: Mapped[bool] = mapped_column(Boolean, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[Source] = mapped_column(_enum(Source, "run_source"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[RunStatus] = mapped_column(_enum(RunStatus, "run_status"))
    rows_inserted: Mapped[int] = mapped_column(Integer, server_default="0")
    rows_updated: Mapped[int] = mapped_column(Integer, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)


class ModelRunKind(StrEnum):
    BACKTEST = "backtest"
    PREDICT = "predict"


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(32))  # "elo"
    kind: Mapped[ModelRunKind] = mapped_column(_enum(ModelRunKind, "model_run_kind"))
    version: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSONB)
    train_through: Mapped[date | None] = mapped_column(Date)  # last finished match used
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    git_sha: Mapped[str | None] = mapped_column(String(64))


class TeamRating(Base):
    """Final rating per team after the run's last finished match."""

    __tablename__ = "team_ratings"
    __table_args__ = (UniqueConstraint("model_run_id", "team_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    rating: Mapped[float] = mapped_column(Double)
    as_of_date: Mapped[date] = mapped_column(Date)


class Prediction(Base):
    """Pre-match H/D/A probabilities. Rows for kicked-off matches are never updated (see
    ``engine.models.store``). The ``official_predictions`` view picks, per (model, match), the
    latest row created before kick-off; ``official_primary_predictions`` keeps the primary model.
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("model_run_id", "match_id"),
        CheckConstraint("abs(p_home + p_draw + p_away - 1) <= 1e-6", name="probs_sum_to_one"),
        CheckConstraint(
            "p_home BETWEEN 0 AND 1 AND p_draw BETWEEN 0 AND 1 AND p_away BETWEEN 0 AND 1",
            name="probs_in_unit_interval",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id", ondelete="RESTRICT"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    p_home: Mapped[float] = mapped_column(Double)
    p_draw: Mapped[float] = mapped_column(Double)
    p_away: Mapped[float] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Setting(Base):
    """Key/value settings. ``primary_model`` names the model whose predictions are official."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id", ondelete="RESTRICT"))
    n_sims: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[date] = mapped_column(Date)  # last finished match included
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    git_sha: Mapped[str | None] = mapped_column(String(64))


class TeamSimulationResult(Base):
    __tablename__ = "team_simulation_results"
    __table_args__ = (UniqueConstraint("simulation_run_id", "team_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE")
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    p_top8: Mapped[float] = mapped_column(Double)
    p_playoff: Mapped[float] = mapped_column(Double)  # league positions 9-24
    p_out: Mapped[float] = mapped_column(Double)  # league positions 25-36
    p_r16: Mapped[float] = mapped_column(Double)
    p_qf: Mapped[float] = mapped_column(Double)
    p_sf: Mapped[float] = mapped_column(Double)
    p_final: Mapped[float] = mapped_column(Double)
    p_win: Mapped[float] = mapped_column(Double)
    expected_points: Mapped[float] = mapped_column(Double)
    position_hist: Mapped[list] = mapped_column(JSONB)  # P(position = k), k = 1..36
