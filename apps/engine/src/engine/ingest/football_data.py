"""football-data.org v4 client and parser (free tier: current season, 10 req/min)."""

import json
import logging
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx

from engine.db.models import MatchStatus, Source, Stage
from engine.ingest.common import (
    ParsedMatch,
    ParsedSeason,
    TeamRef,
    assign_legs,
    is_neutral,
    raw_path,
    season_label,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"
MIN_INTERVAL_S = 6.5
MAX_RETRIES = 3


class FootballDataClient:
    """httpx client with a minimum spacing between calls, 5xx retries and 429 back-off."""

    def __init__(self, token: str, *, timeout: float = 30.0) -> None:
        self._http = httpx.Client(
            base_url=BASE_URL, headers={"X-Auth-Token": token}, timeout=timeout
        )
        self._last_call = 0.0

    def __enter__(self) -> "FootballDataClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self._http.close()

    def _throttle(self) -> None:
        wait = self._last_call + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def get(self, path: str) -> dict[str, Any]:
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                resp = self._http.get(path)
            except httpx.TransportError:
                if attempt == MAX_RETRIES:
                    raise
                logger.warning("transport error on %s, retrying", path)
                time.sleep(2**attempt)
                continue
            if resp.status_code == 429 and attempt < MAX_RETRIES:
                wait = float(
                    resp.headers.get("Retry-After")
                    or resp.headers.get("X-RequestCounter-Reset")
                    or 60
                )
                logger.warning("rate limited on %s, sleeping %.0fs", path, wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                logger.warning("HTTP %s on %s, retrying", resp.status_code, path)
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        raise AssertionError("unreachable")


def fetch(token: str) -> dict[str, Any]:
    """Fetch the whole current CL season (matches + teams) and cache the raw JSON by date."""
    with FootballDataClient(token) as client:
        payload = {
            "matches": client.get("/competitions/CL/matches"),
            "teams": client.get("/competitions/CL/teams"),
        }
    path = raw_path("football_data", f"{date.today().isoformat()}.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("cached %s", path)
    return payload


# football-data area codes (ISO-ish) -> openfootball/FIFA codes; identical codes are omitted.
COUNTRY_CODE_MAP = {
    "BGR": "BUL",
    "CHE": "SUI",
    "DEU": "GER",
    "DNK": "DEN",
    "GRC": "GRE",
    "HRV": "CRO",
    "NLD": "NED",
    "PRT": "POR",
}

_STAGES = {
    "QUALIFICATION": Stage.QUALIFYING,
    "QUALIFICATION_ROUND_1": Stage.QUALIFYING,
    "QUALIFICATION_ROUND_2": Stage.QUALIFYING,
    "QUALIFICATION_ROUND_3": Stage.QUALIFYING,
    "PRELIMINARY_ROUND": Stage.QUALIFYING,
    "PRELIMINARY_SEMI_FINALS": Stage.QUALIFYING,
    "PRELIMINARY_FINAL": Stage.QUALIFYING,
    "PLAYOFF_ROUND": Stage.PLAYOFF_ROUND,
    "PLAYOFF_ROUND_1": Stage.PLAYOFF_ROUND,
    "GROUP_STAGE": Stage.GROUP_STAGE,
    "LEAGUE_STAGE": Stage.LEAGUE_PHASE,
    "LAST_16": Stage.LAST_16,
    "ROUND_OF_16": Stage.LAST_16,
    "QUARTER_FINALS": Stage.QUARTER_FINALS,
    "SEMI_FINALS": Stage.SEMI_FINALS,
    "FINAL": Stage.FINAL,
}

_STATUSES = {
    "FINISHED": MatchStatus.FINISHED,
    "AWARDED": MatchStatus.FINISHED,
    "SCHEDULED": MatchStatus.SCHEDULED,
    "TIMED": MatchStatus.SCHEDULED,
    "IN_PLAY": MatchStatus.SCHEDULED,
    "PAUSED": MatchStatus.SCHEDULED,
    "POSTPONED": MatchStatus.POSTPONED,
    "SUSPENDED": MatchStatus.POSTPONED,
    "CANCELLED": MatchStatus.CANCELLED,
}


def _stage(raw: str, season_start_year: int) -> Stage:
    if raw == "PLAYOFFS":
        # Knockout play-offs after the league phase (2024-25 on); before that "PLAYOFFS" was the
        # last qualifying round.
        return Stage.KNOCKOUT_PLAYOFF if season_start_year >= 2024 else Stage.PLAYOFF_ROUND
    try:
        return _STAGES[raw]
    except KeyError:
        raise ValueError(f"unknown football-data stage {raw!r}") from None


def _status(raw: str) -> MatchStatus:
    try:
        return _STATUSES[raw]
    except KeyError:
        raise ValueError(f"unknown football-data status {raw!r}") from None


def _pair(part: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not part:
        return None, None
    return part.get("home"), part.get("away")


def scores(score: dict[str, Any]) -> dict[str, int | None]:
    """Split a v4 ``score`` object into 90-minute / after-ET / shootout goals.

    v4 ``fullTime`` includes extra time and shootout goals, so for any ``duration`` other than
    REGULAR the 90-minute score is ``regularTime``; after-ET is ``regularTime + extraTime``.
    """
    ft_h, ft_a = _pair(score.get("fullTime"))
    if score.get("duration", "REGULAR") == "REGULAR":
        return {"home_goals_90": ft_h, "away_goals_90": ft_a}
    rt_h, rt_a = _pair(score.get("regularTime"))
    et_h, et_a = _pair(score.get("extraTime"))
    pen_h, pen_a = _pair(score.get("penalties"))
    out: dict[str, int | None] = {"home_goals_90": rt_h, "away_goals_90": rt_a}
    if rt_h is not None and et_h is not None:
        out["home_goals_et"] = rt_h + et_h
        out["away_goals_et"] = rt_a + et_a
    out["home_pens"], out["away_pens"] = pen_h, pen_a
    return out


def _team(raw: dict[str, Any], countries: dict[int, str]) -> TeamRef:
    code = countries.get(raw["id"])
    return TeamRef(
        name=raw["name"],
        country=COUNTRY_CODE_MAP.get(code, code) if code else None,
        fd_team_id=raw["id"],
        short_name=raw.get("shortName"),
        tla=raw.get("tla"),
        crest_url=raw.get("crest"),
    )


def parse(payload: dict[str, Any]) -> ParsedSeason:
    """Parse a cached ``fetch`` payload into one season of matches.

    Matches whose teams are not yet known (TBD knockout slots) are skipped.
    """
    countries = {
        t["id"]: t["area"]["code"]
        for t in payload.get("teams", {}).get("teams", [])
        if t.get("area", {}).get("code")
    }
    raw_matches = payload["matches"]["matches"]
    season_meta = raw_matches[0]["season"] if raw_matches else payload["matches"]["filters"]
    start = date.fromisoformat(season_meta["startDate"])
    label = season_label(start.year)

    matches: list[ParsedMatch] = []
    for m in raw_matches:
        if m["homeTeam"].get("id") is None or m["awayTeam"].get("id") is None:
            continue
        stage = _stage(m["stage"], start.year)
        kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).astimezone(UTC)
        status = _status(m["status"])
        goals = scores(m["score"]) if status is MatchStatus.FINISHED else {}
        matches.append(
            ParsedMatch(
                source=Source.FOOTBALL_DATA,
                source_key=str(m["id"]),
                season=label,
                stage=stage,
                matchday=m.get("matchday"),
                match_date=kickoff.date(),
                kickoff_utc=kickoff,
                home=_team(m["homeTeam"], countries),
                away=_team(m["awayTeam"], countries),
                status=status,
                neutral_venue=is_neutral(label, stage),
                **goals,
            )
        )
    end = season_meta.get("endDate")
    return ParsedSeason(
        label=label,
        start_date=start,
        end_date=date.fromisoformat(end) if end else None,
        matches=assign_legs(matches),
    )
