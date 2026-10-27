"""Database I/O for rating models: load matches, record runs, write ratings and predictions."""

import logging
import math
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import insert

from engine.config import REPO_ROOT
from engine.db.models import (
    Match,
    MatchStatus,
    ModelRun,
    ModelRunKind,
    Prediction,
    Season,
    TeamRating,
)
from engine.models.elo import EloParams, MatchRow

logger = logging.getLogger(__name__)

MODEL = "elo"
MODEL_VERSION = "1"

Probs = tuple[float, float, float]


class PostKickoffUpdateError(RuntimeError):
    """Raised instead of changing a prediction for a match that has already kicked off."""


def load_matches(conn: Connection) -> list[MatchRow]:
    """Finished and scheduled matches; goals are the 90-minute score (None unless finished)."""
    rows = conn.execute(
        select(Match.__table__, Season.label)
        .join(Season, Season.id == Match.season_id)
        .where(Match.status.in_([MatchStatus.FINISHED, MatchStatus.SCHEDULED]))
    ).all()
    out = []
    for m in rows:
        label = m.label
        finished = m.status == MatchStatus.FINISHED
        if finished and (m.home_goals_90 is None or m.away_goals_90 is None):
            raise ValueError(f"finished match {m.id} has no 90-minute score")
        out.append(
            MatchRow(
                id=m.id,
                season=label,
                stage=m.stage,
                match_date=m.match_date,
                kickoff_utc=m.kickoff_utc,
                home_id=m.home_team_id,
                away_id=m.away_team_id,
                home_goals=m.home_goals_90 if finished else None,
                away_goals=m.away_goals_90 if finished else None,
                neutral=m.neutral_venue,
                matchday=m.matchday,
            )
        )
    return out


def git_sha() -> str | None:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{sha}-dirty" if dirty else sha


def create_model_run(
    conn: Connection,
    kind: ModelRunKind,
    params: EloParams,
    train_through: date | None,
    metrics: dict | None,
) -> int:
    return conn.scalar(
        insert(ModelRun)
        .values(
            model=MODEL,
            kind=kind,
            version=MODEL_VERSION,
            params=params.to_dict(),
            train_through=train_through,
            metrics=metrics,
            git_sha=git_sha(),
        )
        .returning(ModelRun.id)
    )


def latest_backtest_params(conn: Connection) -> EloParams | None:
    params = conn.scalar(
        select(ModelRun.params)
        .where(ModelRun.model == MODEL, ModelRun.kind == ModelRunKind.BACKTEST)
        .order_by(ModelRun.id.desc())
        .limit(1)
    )
    return EloParams.from_dict(params) if params else None


def write_team_ratings(
    conn: Connection, run_id: int, ratings: Mapping[int, float], as_of: date
) -> None:
    if ratings:
        conn.execute(
            insert(TeamRating),
            [
                {"model_run_id": run_id, "team_id": t, "rating": r, "as_of_date": as_of}
                for t, r in ratings.items()
            ],
        )


def kickoff_of(kickoff_utc: datetime | None, match_date: date) -> datetime:
    """Kick-off time; without one, midnight UTC of the match date (the conservative choice)."""
    return kickoff_utc or datetime.combine(match_date, time.min, tzinfo=UTC)


@dataclass
class WritePlan:
    upserts: dict[int, Probs] = field(default_factory=dict)
    unchanged: list[int] = field(default_factory=list)
    skipped_started: list[int] = field(default_factory=list)


def _same(a: Probs, b: Probs) -> bool:
    return all(math.isclose(x, y, rel_tol=0, abs_tol=1e-12) for x, y in zip(a, b, strict=True))


def plan_prediction_writes(
    existing: Mapping[int, Probs],
    new: Mapping[int, Probs],
    kickoffs: Mapping[int, datetime],
    now: datetime,
) -> WritePlan:
    """Decide which predictions to write.

    - a changed prediction for a match that has kicked off -> PostKickoffUpdateError
    - a new prediction for a match that has kicked off -> skipped (it would not be pre-match)
    - anything else -> upserted (identical values are left alone)
    """
    plan = WritePlan()
    for match_id, probs in new.items():
        started = kickoffs[match_id] <= now
        if match_id in existing:
            if _same(existing[match_id], probs):
                plan.unchanged.append(match_id)
                continue
            if started:
                raise PostKickoffUpdateError(
                    f"match {match_id} kicked off at {kickoffs[match_id]:%Y-%m-%d %H:%M}Z;"
                    " its prediction cannot change"
                )
        elif started:
            plan.skipped_started.append(match_id)
            continue
        plan.upserts[match_id] = probs
    return plan


def write_predictions(
    conn: Connection, run_id: int, preds: Mapping[int, Probs], now: datetime | None = None
) -> WritePlan:
    """Upsert predictions for one run, refusing to change any for kicked-off matches."""
    now = now or datetime.now(UTC)
    ids = list(preds)
    existing = {
        mid: (h, d, a)
        for mid, h, d, a in conn.execute(
            select(
                Prediction.match_id, Prediction.p_home, Prediction.p_draw, Prediction.p_away
            ).where(Prediction.model_run_id == run_id, Prediction.match_id.in_(ids))
        )
    }
    kickoffs = {
        mid: kickoff_of(ko, d)
        for mid, ko, d in conn.execute(
            select(Match.id, Match.kickoff_utc, Match.match_date).where(Match.id.in_(ids))
        )
    }
    plan = plan_prediction_writes(existing, preds, kickoffs, now)
    if plan.skipped_started:
        logger.warning("skipped %d matches that already kicked off", len(plan.skipped_started))
    if plan.upserts:
        stmt = insert(Prediction).values(
            [
                {"model_run_id": run_id, "match_id": mid, "p_home": h, "p_draw": d, "p_away": a}
                for mid, (h, d, a) in plan.upserts.items()
            ]
        )
        conn.execute(
            stmt.on_conflict_do_update(
                index_elements=["model_run_id", "match_id"],
                set_={
                    "p_home": stmt.excluded.p_home,
                    "p_draw": stmt.excluded.p_draw,
                    "p_away": stmt.excluded.p_away,
                    "created_at": func.now(),
                },
            )
        )
    return plan
