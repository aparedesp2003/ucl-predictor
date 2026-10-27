"""Source-independent parsed records and the derivation rules shared by both sources."""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from engine.config import REPO_ROOT
from engine.db.models import MatchStatus, SeasonFormat, Source, Stage

RAW_DIR = REPO_ROOT / "data" / "raw"

TWO_LEGGED_STAGES = frozenset(
    {
        Stage.QUALIFYING,
        Stage.PLAYOFF_ROUND,
        Stage.KNOCKOUT_PLAYOFF,
        Stage.LAST_16,
        Stage.QUARTER_FINALS,
        Stage.SEMI_FINALS,
    }
)


@dataclass(frozen=True)
class TeamRef:
    name: str
    country: str | None = None  # openfootball code scheme (GER, ESP, ...)
    fd_team_id: int | None = None
    short_name: str | None = None
    tla: str | None = None
    crest_url: str | None = None


@dataclass(frozen=True)
class ParsedMatch:
    source: Source
    source_key: str
    season: str
    stage: Stage
    match_date: date
    kickoff_utc: datetime | None
    home: TeamRef
    away: TeamRef
    status: MatchStatus
    matchday: int | None = None
    leg: int | None = None
    home_goals_90: int | None = None
    away_goals_90: int | None = None
    home_goals_et: int | None = None
    away_goals_et: int | None = None
    home_pens: int | None = None
    away_pens: int | None = None
    neutral_venue: bool = False


@dataclass(frozen=True)
class ParsedSeason:
    label: str
    start_date: date | None
    end_date: date | None
    matches: list[ParsedMatch]

    @property
    def format(self) -> SeasonFormat:
        return season_format(self.label)


def season_format(label: str) -> SeasonFormat:
    return SeasonFormat.LEAGUE_PHASE if label >= "2024-25" else SeasonFormat.GROUP_STAGE


def season_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def is_neutral(season: str, stage: Stage) -> bool:
    """Finals are neutral; 2019-20 QF/SF were single matches in Lisbon (COVID format)."""
    if stage is Stage.FINAL:
        return True
    return season == "2019-20" and stage in (Stage.QUARTER_FINALS, Stage.SEMI_FINALS)


def _pair_key(m: ParsedMatch) -> frozenset[str]:
    return frozenset({m.home.name, m.away.name})


def assign_legs(matches: list[ParsedMatch]) -> list[ParsedMatch]:
    """Set leg 1/2 for two-legged ties; NULL for single matches and non-knockout stages.

    In group/league/final stages leg is always NULL: two group meetings of the same pair are
    not legs of a tie.
    """
    groups: dict[tuple[Stage, frozenset[str]], list[int]] = defaultdict(list)
    for i, m in enumerate(matches):
        if m.stage in TWO_LEGGED_STAGES:
            groups[(m.stage, _pair_key(m))].append(i)

    out = [replace(m, leg=None) for m in matches]
    for idxs in groups.values():
        if len(idxs) != 2:
            continue
        ordered = sorted(idxs, key=lambda i: matches[i].match_date)
        for leg, i in enumerate(ordered, start=1):
            out[i] = replace(out[i], leg=leg)
    return out


def raw_path(*parts: str) -> Path:
    path = RAW_DIR.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
