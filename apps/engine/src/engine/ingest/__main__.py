"""Ingest CLI.

uv run python -m engine.ingest football-data [--file CACHED.json]
uv run python -m engine.ingest openfootball --from 2011-12 --to 2025-26 [--refresh]
uv run python -m engine.ingest report
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import Engine, func, select

from engine.config import get_settings
from engine.db import get_engine
from engine.db.models import IngestRun, Match, MatchStatus, Season, Source, Team
from engine.ingest import football_data, openfootball
from engine.ingest.common import RAW_DIR
from engine.ingest.load import LoadStats, build_resolver, finish_run, load_season, start_run

logger = logging.getLogger("engine.ingest")


def _print_stats(label: str, stats: LoadStats) -> None:
    print(
        f"{label}: matches +{stats.matches_inserted} ~{stats.matches_updated}"
        f" skipped {stats.matches_skipped} | teams +{stats.teams_inserted} ~{stats.teams_updated}"
        f" | aliases +{stats.aliases_inserted}"
    )


def _finish(engine: Engine, run_id: int, stats: LoadStats) -> int:
    finish_run(engine, run_id, stats)
    _print_stats("total", stats)
    if stats.resolved_by:
        print("openfootball names resolved by:", dict(stats.resolved_by))
    for name, n in sorted(stats.unresolved.items()):
        print(f"UNRESOLVED {name} ({n} refs)")
    return 1 if stats.unresolved else 0


def cmd_football_data(args: argparse.Namespace) -> int:
    if args.file:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    else:
        token = get_settings().football_data_token
        if not token:
            sys.exit("FOOTBALL_DATA_TOKEN is not set; add it to the repo-root .env")
        payload = football_data.fetch(token)
    season = football_data.parse(payload)

    engine = get_engine()
    run_id = start_run(engine, Source.FOOTBALL_DATA)
    stats = LoadStats()
    try:
        with engine.begin() as conn:
            stats = load_season(conn, season, build_resolver(conn))
    except Exception as exc:
        finish_run(engine, run_id, stats, error=repr(exc))
        raise
    _print_stats(season.label, stats)
    return _finish(engine, run_id, stats)


def cmd_openfootball(args: argparse.Namespace) -> int:
    seasons = openfootball.season_range(args.from_, args.to)
    engine = get_engine()
    run_id = start_run(engine, Source.OPENFOOTBALL)
    total = LoadStats()
    try:
        with engine.connect() as conn:
            resolver = build_resolver(conn)
        for label in seasons:
            parsed = openfootball.parse_season(
                label, openfootball.download(label, refresh=args.refresh)
            )
            with engine.begin() as conn:  # one transaction per season
                stats = load_season(conn, parsed, resolver)
            _print_stats(label, stats)
            total += stats
    except Exception as exc:
        finish_run(engine, run_id, total, error=repr(exc))
        raise
    return _finish(engine, run_id, total)


def _table(title: str, header: tuple[str, ...], rows: list[tuple]) -> None:
    print(f"\n== {title}")
    if not rows:
        print("(none)")
        return
    cells = [tuple(str(c) for c in r) for r in [header, *rows]]
    widths = [max(len(r[i]) for r in cells) for i in range(len(header))]
    for r in cells:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip())


def _unresolved_names(conn, resolver) -> list[tuple[str, str]]:
    """Names in the cached raw files that have no exact alias / fd id in the DB."""
    out: set[tuple[str, str]] = set()
    for path in sorted((RAW_DIR / "openfootball").glob("*.txt")):
        label = path.stem.removesuffix("-q")
        text = path.read_text(encoding="utf-8")
        for m in openfootball.parse_text(label, text, qualifying_file=path.stem.endswith("-q")):
            for ref in (m.home, m.away):
                if not resolver.has_alias(Source.OPENFOOTBALL, ref.name):
                    out.add(("openfootball", f"{ref.name} ({ref.country})"))
    fd_files = sorted((RAW_DIR / "football_data").glob("*.json"))
    if fd_files:
        known = set(conn.scalars(select(Team.fd_team_id).where(Team.fd_team_id.is_not(None))))
        payload = json.loads(fd_files[-1].read_text(encoding="utf-8"))
        for m in football_data.parse(payload).matches:
            for ref in (m.home, m.away):
                if ref.fd_team_id not in known:
                    out.add(("football_data", f"{ref.name} [{ref.fd_team_id}]"))
    return sorted(out)


def cmd_report(_: argparse.Namespace) -> int:
    with get_engine().connect() as conn:
        resolver = build_resolver(conn)
        per_season = conn.execute(
            select(Season.label, Season.format, Match.source, func.count())
            .join(Match, Match.season_id == Season.id)
            .group_by(Season.label, Season.format, Match.source)
            .order_by(Season.label)
        ).all()
        _table("matches per season", ("season", "format", "source", "matches"), per_season)

        detail = conn.execute(
            select(Season.label, Match.stage, Match.status, func.count())
            .join(Match, Match.season_id == Season.id)
            .group_by(Season.label, Match.stage, Match.status)
            .order_by(Season.label, Match.stage, Match.status)
        ).all()
        _table("matches per season / stage / status", ("season", "stage", "status", "n"), detail)

        n_matches = conn.scalar(select(func.count()).select_from(Match))
        n_teams = conn.scalar(select(func.count()).select_from(Team))
        n_fd = conn.scalar(select(func.count()).where(Team.fd_team_id.is_not(None)))
        print(f"\ntotals: {n_matches} matches, {n_teams} teams ({n_fd} with fd_team_id)")

        unresolved = _unresolved_names(conn, resolver)
        _table("unresolved team names", ("source", "name"), unresolved)

        _table(
            "possible duplicate teams (same country, similar name)",
            ("country", "team_a", "team_b"),
            resolver.possible_duplicates(),
        )

        home, away = Team.__table__.alias("h"), Team.__table__.alias("a")
        base = (
            select(Season.label, Match.stage, Match.match_date, home.c.name, away.c.name)
            .join(Season, Season.id == Match.season_id)
            .join(home, home.c.id == Match.home_team_id)
            .join(away, away.c.id == Match.away_team_id)
            .order_by(Match.match_date)
        )
        missing = conn.execute(
            base.where(
                Match.status == MatchStatus.FINISHED,
                Match.home_goals_90.is_(None) | Match.away_goals_90.is_(None),
            )
        ).all()
        _table("finished matches missing 90' scores", ("season", "stage", "date", "home", "away"),
               missing)  # fmt: skip
        stale = conn.execute(
            base.where(Match.status == MatchStatus.SCHEDULED, Match.match_date < date.today())
        ).all()
        _table("past-dated matches not finished", ("season", "stage", "date", "home", "away"),
               stale)  # fmt: skip

        runs = conn.execute(
            select(
                IngestRun.id,
                IngestRun.source,
                IngestRun.status,
                IngestRun.rows_inserted,
                IngestRun.rows_updated,
                IngestRun.started_at,
            )
            .order_by(IngestRun.id.desc())
            .limit(6)
        ).all()
        _table("recent ingest runs", ("id", "source", "status", "ins", "upd", "started"), runs)
    return 1 if unresolved else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    fd = sub.add_parser("football-data", help="current season from football-data.org")
    fd.add_argument("--file", help="load a cached raw JSON instead of calling the API")
    fd.set_defaults(func=cmd_football_data)

    of = sub.add_parser("openfootball", help="past seasons from openfootball Football.TXT")
    of.add_argument("--from", dest="from_", default="2011-12")
    of.add_argument("--to", default="2025-26")
    of.add_argument("--refresh", action="store_true", help="re-download cached files")
    of.set_defaults(func=cmd_openfootball)

    rp = sub.add_parser("report", help="coverage and data-quality report")
    rp.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
