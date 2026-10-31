"""Markdown report of a pipeline run (for $GITHUB_STEP_SUMMARY): outcome, newly finished matches,
next matchday's primary-model predictions, simulation top 10 and the season's scoreboard."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text

_METRICS = ("log_loss", "rps", "brier", "accuracy")


@dataclass
class Report:
    run: dict[str, Any]  # pipeline_runs row
    season: str | None = None
    primary_model: str | None = None
    next_matchday: str | None = None
    next_predictions: list[dict[str, Any]] = field(default_factory=list)
    simulation_run_id: int | None = None
    simulation_as_of: str | None = None
    simulation_top: list[dict[str, Any]] = field(default_factory=list)
    scoreboard: list[dict[str, Any]] = field(default_factory=list)


def _rows(conn: Connection, sql: str, **params) -> list[dict[str, Any]]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def load_report(conn: Connection, run_id: int | None = None) -> Report:
    runs = _rows(
        conn,
        "SELECT * FROM pipeline_runs WHERE id = :id OR (CAST(:id AS int) IS NULL)"
        " ORDER BY id DESC LIMIT 1",
        id=run_id,
    )
    if not runs:
        raise RuntimeError(f"no pipeline run {run_id if run_id is not None else 'recorded'}")
    report = Report(run=runs[0])
    report.primary_model = conn.scalar(
        text("SELECT value FROM settings WHERE key = 'primary_model'")
    )
    report.season = conn.scalar(
        text(
            "SELECT s.label FROM seasons s JOIN matches m ON m.season_id = s.id"
            " WHERE m.source = 'football_data' ORDER BY s.label DESC LIMIT 1"
        )
    )

    nxt = _rows(
        conn,
        """
        SELECT m.season_id, m.stage, m.matchday FROM official_primary_predictions o
        JOIN matches m ON m.id = o.match_id
        WHERE m.status = 'SCHEDULED' AND m.kickoff_utc > now()
        ORDER BY m.kickoff_utc, m.id LIMIT 1
        """,
    )
    if nxt:
        n = nxt[0]
        report.next_matchday = (
            f"{n['stage']} matchday {n['matchday']}" if n["matchday"] else n["stage"]
        )
        report.next_predictions = _rows(
            conn,
            """
            SELECT m.kickoff_utc, h.name AS home, a.name AS away,
                   o.p_home, o.p_draw, o.p_away, o.model_run_id
            FROM official_primary_predictions o
            JOIN matches m ON m.id = o.match_id
            JOIN teams h ON h.id = m.home_team_id
            JOIN teams a ON a.id = m.away_team_id
            WHERE m.season_id = :season AND m.stage = :stage
              AND m.matchday IS NOT DISTINCT FROM :md AND m.status = 'SCHEDULED'
            ORDER BY m.kickoff_utc, m.id
            """,
            season=n["season_id"],
            stage=n["stage"],
            md=n["matchday"],
        )

    sim = report.run.get("simulation_run_id") or conn.scalar(
        text("SELECT max(id) FROM simulation_runs")
    )
    if sim is not None:
        report.simulation_run_id = sim
        report.simulation_as_of = str(
            conn.scalar(text("SELECT as_of FROM simulation_runs WHERE id = :id"), {"id": sim})
        )
        report.simulation_top = _rows(
            conn,
            """
            SELECT t.name AS team, r.expected_points, r.p_top8, r.p_playoff, r.p_r16, r.p_qf,
                   r.p_sf, r.p_final, r.p_win
            FROM team_simulation_results r JOIN teams t ON t.id = r.team_id
            WHERE r.simulation_run_id = :id
            ORDER BY r.p_win DESC, r.expected_points DESC LIMIT 10
            """,
            id=sim,
        )
    if report.season:
        report.scoreboard = _rows(
            conn,
            "SELECT * FROM model_scoreboard WHERE season = :s ORDER BY model",
            s=report.season,
        )
    return report


def _table(header: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _when(ts: datetime | None) -> str:
    return f"{ts:%Y-%m-%d %H:%M}Z" if ts else "-"


def render(report: Report) -> str:
    run = report.run
    summary = run.get("summary") or {}
    changes = summary.get("changes") or {}
    changed = {True: "yes", False: "no", None: "-"}[run.get("changed")]
    out = [f"## Matchday pipeline run {run['id']}: `{run['status']}`", ""]
    facts = [
        ("trigger", run.get("trigger")),
        ("started", _when(run.get("started_at"))),
        ("finished", _when(run.get("finished_at"))),
        ("changed", changed),
        ("decision", summary.get("decision", "-")),
        ("ingest run", run.get("ingest_run_id") or "-"),
        ("model runs", ", ".join(map(str, run.get("model_run_ids") or [])) or "-"),
        ("simulation run", run.get("simulation_run_id") or "-"),
        ("timings (s)", ", ".join(f"{k} {v}" for k, v in summary.get("timings_s", {}).items())),
    ]
    out.append(_table(["", ""], [[k, v or "-"] for k, v in facts]))
    if run.get("error"):
        failed_step = summary.get("step", "?")
        out += ["", f"**Failed in `{failed_step}`:**", "", "```", str(run["error"]), "```"]

    finished = changes.get("newly_finished") or []
    out += ["", f"### Matches newly finished ({len(finished)})", ""]
    out += [f"- {m}" for m in finished] or ["None."]
    others = {k: v for k, v in changes.items() if k != "newly_finished" and v}
    for kind, items in others.items():
        out += ["", f"<details><summary>{kind.replace('_', ' ')} ({len(items)})</summary>", ""]
        out += [f"- {m}" for m in items] + ["", "</details>"]

    title = f"### Next matchday: {report.next_matchday}" if report.next_matchday else None
    out += ["", title or "### Next matchday", ""]
    if report.next_predictions:
        out.append(f"Primary model `{report.primary_model}`, official pre-kick-off predictions.")
        out.append("")
        out.append(
            _table(
                ["kick-off (UTC)", "home", "away", "H", "D", "A"],
                [
                    [_when(p["kickoff_utc"]), p["home"], p["away"],
                     _pct(p["p_home"]), _pct(p["p_draw"]), _pct(p["p_away"])]
                    for p in report.next_predictions
                ],
            )
        )  # fmt: skip
    else:
        out.append("No upcoming match has an official primary-model prediction.")

    out += ["", f"### Simulation top 10 (run {report.simulation_run_id or '-'})", ""]
    if report.simulation_top:
        out.append(f"Results through {report.simulation_as_of}.")
        out.append("")
        out.append(
            _table(
                ["#", "team", "xPts", "top 8", "9-24", "R16", "QF", "SF", "final", "win"],
                [
                    [i, r["team"], f"{r['expected_points']:.1f}",
                     *(_pct(r[k]) for k in ("p_top8", "p_playoff", "p_r16", "p_qf", "p_sf",
                                            "p_final", "p_win"))]
                    for i, r in enumerate(report.simulation_top, 1)
                ],
            )
        )  # fmt: skip
    else:
        out.append("No simulation run yet.")

    out += ["", f"### Scoreboard {report.season or ''}".rstrip(), ""]
    if report.scoreboard:
        out.append(
            _table(
                ["model", "n", *_METRICS, *(f"uniform {m}" for m in _METRICS)],
                [
                    [s["model"], s["n"], *(f"{float(s[m]):.4f}" for m in _METRICS),
                     *(f"{float(s['uniform_' + m]):.4f}" for m in _METRICS)]
                    for s in report.scoreboard
                ],
            )
        )  # fmt: skip
    else:
        out.append("No finished match this season has an official (pre-kick-off) prediction yet.")
    return "\n".join(out) + "\n"
