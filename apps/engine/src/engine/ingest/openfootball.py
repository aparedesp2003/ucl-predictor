"""openfootball/champions-league (Football.TXT) downloader and parser for past seasons.

Kick-off times in Football.TXT are Central European local time; we convert them to UTC with
``Europe/Berlin`` (an assumption: a few matches played elsewhere may be listed in local time).
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import httpx

from engine.db.models import MatchStatus, Source, Stage
from engine.ingest.common import (
    ParsedMatch,
    ParsedSeason,
    TeamRef,
    assign_legs,
    is_neutral,
    raw_path,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/openfootball/champions-league/master"
LOCAL_TZ = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")

# (remote file, local cache suffix); qualifiers (clq.txt) only exist for some seasons.
FILES = (("cl.txt", ""), ("clq.txt", "-q"))


def season_range(first: str, last: str) -> list[str]:
    start, end = int(first[:4]), int(last[:4])
    if end < start:
        raise ValueError(f"--from {first} is after --to {last}")
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(start, end + 1)]


def download(season: str, *, refresh: bool = False) -> list[str]:
    """Return the season's Football.TXT files (main tournament first), using the local cache."""
    texts = []
    with httpx.Client(timeout=30.0, follow_redirects=True) as http:
        for remote, suffix in FILES:
            path = raw_path("openfootball", f"{season}{suffix}.txt")
            if path.exists() and not refresh:
                texts.append(path.read_text(encoding="utf-8"))
                continue
            resp = http.get(f"{BASE_URL}/{season}/{remote}")
            if resp.status_code == 404:
                if remote == "cl.txt":
                    raise FileNotFoundError(f"no {remote} for {season}")
                continue
            resp.raise_for_status()
            text = resp.content.decode("utf-8")
            path.write_text(text, encoding="utf-8", newline="\n")
            logger.info("cached %s", path)
            texts.append(text)
    return texts


_MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
_DATE_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) (\d{1,2})(?: (\d{4}))?$"
)
_MATCH_RE = re.compile(
    r"^\s+(?:(?P<time>\d{1,2}:\d{2})\s+)?"
    r"(?P<home>\S.*?) \((?P<hc>[A-Z]{3})\)\s+v\s+(?P<away>\S.*?) \((?P<ac>[A-Z]{3})\)"
    r"\s*(?P<score>.*?)\s*$"
)
_REGULAR_RE = re.compile(r"(?P<ft>\d+-\d+)(?: \((?P<ht>\d+-\d+)\))?")
_EXTRA_RE = re.compile(
    r"(?:(?P<pen>\d+-\d+) pen\. )?(?P<et>\d+-\d+) a\.e\.t\. \((?P<ft>\d+-\d+)(?:, \d+-\d+)?\)"
)
_MATCHDAY_RE = re.compile(r"Matchday (\d+)$")


@dataclass(frozen=True)
class Score:
    """Goals per the 90-minute rule (see ``engine.db.models.Match``)."""

    ft: tuple[int, int]
    et: tuple[int, int] | None = None
    pens: tuple[int, int] | None = None


def _goals(text: str) -> tuple[int, int]:
    home, away = text.split("-")
    return int(home), int(away)


def parse_score(text: str) -> Score | None:
    """Parse the score column; ``None`` means the match has no result yet.

    ``F (H)`` -> 90' = F. ``E a.e.t. (F, H)`` -> 90' = F, after ET = E.
    ``P pen. E a.e.t. (F, H)`` adds the shootout P. When ``E`` is 0-0 the source writes ``(0-0)``
    alone, which is then the 90-minute score too.
    """
    text = text.strip()
    if not text:
        return None
    if m := _REGULAR_RE.fullmatch(text):
        return Score(ft=_goals(m["ft"]))
    if m := _EXTRA_RE.fullmatch(text):
        return Score(
            ft=_goals(m["ft"]),
            et=_goals(m["et"]),
            pens=_goals(m["pen"]) if m["pen"] else None,
        )
    raise ValueError(f"unparseable score {text!r}")


def parse_stage(heading: str, *, qualifying_file: bool) -> tuple[Stage, int | None]:
    """Map a ``▪ heading`` to (stage, matchday)."""
    h = heading.strip()
    matchday = int(m[1]) if (m := _MATCHDAY_RE.search(h)) else None
    if qualifying_file:
        if re.fullmatch(r"(?:Round \d|\d\. Round)", h):
            return Stage.QUALIFYING, None
        if h in ("Playoffs", "Play-offs"):
            return Stage.PLAYOFF_ROUND, None
    else:
        if re.fullmatch(r"(?:Group|Gruppe) [A-H]", h):
            return Stage.GROUP_STAGE, None
        if h.startswith("Group, Matchday"):
            return Stage.GROUP_STAGE, matchday
        if h.startswith("League, Matchday"):
            return Stage.LEAGUE_PHASE, matchday
        if h.startswith("Playoffs, Matchday"):
            return Stage.KNOCKOUT_PLAYOFF, None
        knockout = {
            "Round of 16": Stage.LAST_16,
            "Quarterfinals": Stage.QUARTER_FINALS,
            "Semifinals": Stage.SEMI_FINALS,
            "Final": Stage.FINAL,
        }
        if (stage := knockout.get(h.removeprefix("Finals, "))) is not None:
            return stage, None
    raise ValueError(f"unknown openfootball heading {heading!r}")


def parse_text(season: str, text: str, *, qualifying_file: bool = False) -> list[ParsedMatch]:
    """Parse one Football.TXT file. Legs are not assigned here (see ``parse_season``)."""
    start_year = int(season[:4])
    stage: Stage | None = None
    matchday: int | None = None
    day: date | None = None
    kickoff: time | None = None
    last_year = start_year
    matches: list[ParsedMatch] = []

    for lineno, line in enumerate(text.splitlines(), 1):
        line = re.sub(r"\s+@\s.*$", "", line.rstrip())
        if not line.strip() or line.startswith(("#", "=")):
            continue
        try:
            if line.startswith("▪"):
                stage, matchday = parse_stage(line[1:], qualifying_file=qualifying_file)
            elif m := _DATE_RE.match(line):
                # A missing year defaults by month (Jul-Dec: start year, Jan-Jun: next year), but
                # never before the last year written out: 2019-20 resumed in Aug 2020.
                month = _MONTHS[m[1]]
                if m[3]:
                    year = last_year = int(m[3])
                else:
                    year = max(start_year if month >= 7 else start_year + 1, last_year)
                day, kickoff = date(year, month, int(m[2])), None
            elif m := _MATCH_RE.match(line):
                if stage is None or day is None:
                    raise ValueError("match before any heading/date")
                if m["time"]:
                    kickoff = time.fromisoformat(m["time"].zfill(5))
                matches.append(_match(season, stage, matchday, day, kickoff, m))
            else:
                raise ValueError("unrecognized line")
        except ValueError as exc:
            raise ValueError(f"{season} line {lineno}: {exc}: {line!r}") from None
    return matches


def _match(
    season: str,
    stage: Stage,
    matchday: int | None,
    day: date,
    kickoff: time | None,
    m: re.Match[str],
) -> ParsedMatch:
    home, away = m["home"].strip(), m["away"].strip()
    score = parse_score(m["score"])
    kickoff_utc = (
        datetime.combine(day, kickoff, tzinfo=LOCAL_TZ).astimezone(UTC) if kickoff else None
    )
    goals: dict[str, int | None] = {}
    if score:
        goals["home_goals_90"], goals["away_goals_90"] = score.ft
        if score.et:
            goals["home_goals_et"], goals["away_goals_et"] = score.et
        if score.pens:
            goals["home_pens"], goals["away_pens"] = score.pens
    return ParsedMatch(
        source=Source.OPENFOOTBALL,
        source_key=f"{season}|{stage.value}|{day.isoformat()}|{home}|{away}",
        season=season,
        stage=stage,
        matchday=matchday,
        match_date=day,
        kickoff_utc=kickoff_utc,
        home=TeamRef(name=home, country=m["hc"]),
        away=TeamRef(name=away, country=m["ac"]),
        status=MatchStatus.FINISHED if score else MatchStatus.SCHEDULED,
        neutral_venue=is_neutral(season, stage),
        **goals,
    )


def parse_season(season: str, texts: list[str]) -> ParsedSeason:
    """Parse ``download`` output: texts[0] is cl.txt, an optional texts[1] is clq.txt."""
    matches: list[ParsedMatch] = []
    for i, text in enumerate(texts):
        matches += parse_text(season, text, qualifying_file=i > 0)
    dates = [m.match_date for m in matches]
    return ParsedSeason(
        label=season,
        start_date=min(dates, default=None),
        end_date=max(dates, default=None),
        matches=assign_legs(matches),
    )
