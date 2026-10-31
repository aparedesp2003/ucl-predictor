"""Matchday pipeline CLI.

uv run python -m engine.pipeline run [--force] [--dry-run] [--trigger local|manual|schedule]
uv run python -m engine.pipeline summary [--run-id N]   # markdown report of a run
"""

import argparse
import logging
import os
import sys

from engine.cli import print_table
from engine.config import get_settings
from engine.db import get_engine
from engine.db.models import PipelineTrigger
from engine.pipeline import orchestrator
from engine.pipeline.db import DbRunLog, DbSteps
from engine.pipeline.orchestrator import Outcome
from engine.pipeline.summary import load_report, render

logger = logging.getLogger("engine.pipeline")


def _print_outcome(outcome: Outcome, dry_run: bool) -> None:
    s = outcome.summary
    print_table(
        "would change (dry run)" if dry_run else "changes from this ingest",
        ("kind", "n", "examples"),
        [
            (kind, len(items), "; ".join(items[:3]) + (" ..." if len(items) > 3 else ""))
            for kind, items in s.get("changes", {}).items()
        ],
    )
    will_run = bool(outcome.decision and outcome.decision.run)
    if outcome.decision:
        print(f"\ndecision: {'run' if will_run else 'skip'} ({outcome.decision.reason})")
    if dry_run:
        verdict = "predict + simulate" if will_run else "skip"
        print(f"dry run: nothing written; a real run would {verdict}")
        return
    print_table(
        f"pipeline_runs id {outcome.run_id}",
        ("field", "value"),
        [
            ("status", outcome.status.value),
            ("changed", outcome.changed),
            ("ingest_run_id", outcome.ingest_run_id),
            ("model_run_ids", outcome.model_run_ids or None),
            ("simulation_run_id", outcome.simulation_run_id),
            ("timings_s", s.get("timings_s")),
            ("error", outcome.error),
        ],
    )


def cmd_run(args: argparse.Namespace) -> int:
    token = get_settings().football_data_token
    if not token:
        sys.exit("FOOTBALL_DATA_TOKEN is not set")
    engine = get_engine()
    steps = DbSteps(engine, token)
    if args.dry_run:
        outcome = orchestrator.dry_run(steps, args.force)
    else:
        trigger = PipelineTrigger(args.trigger)
        outcome = orchestrator.run(steps, DbRunLog(engine), trigger, args.force)
        if gh_output := os.environ.get("GITHUB_OUTPUT"):
            with open(gh_output, "a", encoding="utf-8") as f:
                f.write(f"run_id={outcome.run_id}\nstatus={outcome.status.value}\n")
    _print_outcome(outcome, args.dry_run)
    return outcome.exit_code


def cmd_summary(args: argparse.Namespace) -> int:
    with get_engine().connect() as conn:
        report = load_report(conn, args.run_id)
    sys.stdout.write(render(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="ingest, and predict + simulate if anything changed")
    run.add_argument("--force", action="store_true", help="predict + simulate even if unchanged")
    run.add_argument(
        "--dry-run", action="store_true", help="fetch and report what would change; write nothing"
    )
    run.add_argument(
        "--trigger", choices=[t.value for t in PipelineTrigger], default=PipelineTrigger.LOCAL.value
    )
    run.set_defaults(func=cmd_run)

    sm = sub.add_parser("summary", help="markdown report of a pipeline run (default: latest)")
    sm.add_argument("--run-id", type=int, default=None)
    sm.set_defaults(func=cmd_summary)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
