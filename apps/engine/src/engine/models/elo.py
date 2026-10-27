"""Elo ratings from 90-minute UCL results. Pure functions; no database access.

Ratings are zero-sum within a season. At the first match of each new season every rated team is
pulled toward the mean rating by ``season_regression``. Matches are processed in
``(match_date, kickoff_utc, id)`` order, qualifiers included.

Teams first seen in the first processed season start at ``BASE_RATING``; later debutants start at
``new_team_rating``. (Seeding everyone at ``new_team_rating`` would only translate all ratings by a
constant, leaving every prediction unchanged.)
"""

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from engine.db.models import Stage

_MIN_KICKOFF = datetime.min.replace(tzinfo=UTC)

HOME, DRAW, AWAY = 0, 1, 2

BASE_RATING = 1500.0


@dataclass(frozen=True)
class MatchRow:
    """DB-free view of a match. Goals are the 90-minute score; None until finished."""

    id: int
    season: str  # "2024-25"
    stage: Stage
    match_date: date
    kickoff_utc: datetime | None
    home_id: int
    away_id: int
    home_goals: int | None
    away_goals: int | None
    neutral: bool = False
    matchday: int | None = None

    @property
    def finished(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def result(self) -> int:
        """HOME / DRAW / AWAY class index from the 90-minute score."""
        assert self.home_goals is not None and self.away_goals is not None
        if self.home_goals > self.away_goals:
            return HOME
        return DRAW if self.home_goals == self.away_goals else AWAY


@dataclass(frozen=True)
class EloParams:
    k: float = 20.0
    home_adv: float = 50.0
    new_team_rating: float = 1500.0
    season_regression: float = 0.2
    use_goal_diff: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EloParams":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


DEFAULT_PARAMS = EloParams()


def sort_key(m: MatchRow) -> tuple[date, datetime, int]:
    return (m.match_date, m.kickoff_utc or _MIN_KICKOFF, m.id)


def rating_diff(r_home: float, r_away: float, home_adv: float, neutral: bool) -> float:
    """Home minus away rating, including home advantage unless the venue is neutral."""
    return r_home + (0.0 if neutral else home_adv) - r_away


def expected_home(r_home: float, r_away: float, home_adv: float, neutral: bool) -> float:
    return 1.0 / (1.0 + 10 ** (-rating_diff(r_home, r_away, home_adv, neutral) / 400))


def outcome_score(home_goals: int, away_goals: int) -> float:
    if home_goals > away_goals:
        return 1.0
    return 0.5 if home_goals == away_goals else 0.0


def goal_diff_multiplier(goal_diff: int, use_goal_diff: bool) -> float:
    gd = abs(goal_diff)
    if not use_goal_diff or gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11 + gd) / 8


def update(
    r_home: float,
    r_away: float,
    home_goals: int,
    away_goals: int,
    neutral: bool,
    params: EloParams,
) -> tuple[float, float]:
    """Post-match ratings. The home gain equals the away loss (zero-sum)."""
    expected = expected_home(r_home, r_away, params.home_adv, neutral)
    g = goal_diff_multiplier(home_goals - away_goals, params.use_goal_diff)
    delta = params.k * g * (outcome_score(home_goals, away_goals) - expected)
    return r_home + delta, r_away - delta


def regress_to_mean(ratings: dict[int, float], fraction: float) -> dict[int, float]:
    """r = mean + (1 - fraction) * (r - mean), mean over all rated teams."""
    if not ratings:
        return {}
    mean = sum(ratings.values()) / len(ratings)
    return {t: mean + (1 - fraction) * (r - mean) for t, r in ratings.items()}


@dataclass
class EloState:
    """Running ratings. Call ``pre_match`` then ``apply`` for each match, in ``sort_key`` order."""

    params: EloParams
    ratings: dict[int, float] = field(default_factory=dict)
    season: str | None = None
    first_season: str | None = None

    def _rating(self, team_id: int) -> float:
        if team_id not in self.ratings:
            founding = self.season == self.first_season
            self.ratings[team_id] = BASE_RATING if founding else self.params.new_team_rating
        return self.ratings[team_id]

    def _enter_season(self, season: str) -> None:
        if season == self.season:
            return
        if self.season is None:
            self.first_season = season
        else:
            self.ratings = regress_to_mean(self.ratings, self.params.season_regression)
        self.season = season

    def pre_match(self, m: MatchRow) -> float:
        """Rating difference (incl. home advantage) before ``m``; enters m's season if new."""
        self._enter_season(m.season)
        return rating_diff(
            self._rating(m.home_id), self._rating(m.away_id), self.params.home_adv, m.neutral
        )

    def apply(self, m: MatchRow) -> None:
        assert m.home_goals is not None and m.away_goals is not None
        self._enter_season(m.season)
        self.ratings[m.home_id], self.ratings[m.away_id] = update(
            self._rating(m.home_id),
            self._rating(m.away_id),
            m.home_goals,
            m.away_goals,
            m.neutral,
            self.params,
        )


def run(matches: Iterable[MatchRow], params: EloParams) -> EloState:
    """Ratings after every finished match in ``matches``."""
    state = EloState(params)
    for m in sorted((m for m in matches if m.finished), key=sort_key):
        state.apply(m)
    return state
