"""Season simulator CLI.

uv run python -m engine.simulate run [--n 10000] [--seed 42] [--sigma S]
"""

import argparse
import logging
import sys
import time

from sqlalchemy import select

from engine.cli import print_table
from engine.db import get_engine
from engine.db.models import Team
from engine.models.report import official_scheduled, print_prob_diff
from engine.models.store import get_primary_model, latest_backtest_params, load_matches
from engine.simulate.engine import SimResult, simulate
from engine.simulate.store import SIM_MODEL, load_inputs, season_formats, write_results
from engine.simulate.uncertainty import SEASONS, default_sigma, rating_drift

logger = logging.getLogger("engine.simulate")


def invariants(res: SimResult) -> list[tuple[str, float, float]]:
    """(quantity, sum over teams, expected): exact by construction."""
    return [
        ("P(win)", res.prob("win").sum(), 1),
        ("P(final)", res.prob("final").sum(), 2),
        ("P(SF)", res.prob("sf").sum(), 4),
        ("P(QF)", res.prob("qf").sum(), 8),
        ("P(R16)", res.prob("r16").sum(), 16),
        ("P(top 8)", res.p_top8.sum(), 8),
        ("P(9-24)", res.p_playoff.sum(), 16),
        ("P(25-36)", res.p_out.sum(), 12),
    ]


def cmd_run(args: argparse.Namespace) -> int:
    engine = get_engine()
    with engine.connect() as conn:
        inputs = load_inputs(conn)
        primary = get_primary_model(conn)
        names = dict(conn.execute(select(Team.id, Team.name)).all())
        elo, shrink = official_scheduled(conn, "elo"), official_scheduled(conn, SIM_MODEL)
        if args.sigma is None:
            drift = rating_drift(load_matches(conn), latest_backtest_params(conn))
            formats = season_formats(conn)
    if args.sigma is None:
        choice = default_sigma(drift, formats, inputs.season)
        print_table(
            f"Elo drift from 3rd group/league match to season end ({SEASONS[0]}..{SEASONS[1]})",
            ("season", "format", "teams", "std", "used"),
            [
                (s, formats[s], n, f"{sd:.1f}", "*" if s in choice.seasons else "")
                for s, (sd, n) in choice.pooled.per_season.items()
            ],
        )
        sigma = choice.sigma
        print(
            f"sigma = {sigma:.1f} Elo points from {choice.basis} ({inputs.season} is"
            f" {formats[inputs.season]}); pooled over all seasons = {choice.pooled.sigma:.1f}"
        )
    else:
        sigma = args.sigma
        print(f"sigma = {sigma:.1f} Elo points (--sigma override)")

    p = inputs.params
    print(
        f"{inputs.season}: {len(inputs.fixtures) - inputs.n_remaining} league matches played,"
        f" {inputs.n_remaining} to simulate; ratings as of {inputs.as_of}"
    )
    print(
        f"scorelines from {SIM_MODEL} (predict run {inputs.model_run_id}):"
        f" shrink s = {inputs.shrink:.4f}, a = {p.a:.3f}, h = {p.h:.3f}, b*s = {p.b:.3f},"
        f" rho = {p.rho:.3f}"
    )
    if primary != SIM_MODEL:
        print(
            f"NOTE: primary model for match predictions is {primary}, not {SIM_MODEL};"
            " the simulator needs goal rates, so it uses the shrink-calibrated Poisson model."
        )

    start = time.perf_counter()
    res = simulate(inputs.fixtures, inputs.ratings, p, n_sims=args.n, seed=args.seed, sigma=sigma)
    runtime = time.perf_counter() - start
    print(f"{args.n} simulations (seed {args.seed}) in {runtime:.2f} s")

    checks = invariants(res)
    print_table(
        "invariants (sum over 36 teams)",
        ("quantity", "sum", "expected", "ok"),
        [(q, f"{s:.6f}", e, "yes" if abs(s - e) < 1e-9 else "NO") for q, s, e in checks],
    )

    order = sorted(
        range(len(inputs.team_ids)),
        key=lambda i: (-res.prob("win")[i], -res.expected_points[i]),
    )
    print_table(
        "simulated outcomes",
        ("team", "xPts", "P top8", "P 9-24", "P out", "P R16", "P QF", "P SF", "P final", "P win"),
        [
            (names[inputs.team_ids[i]], f"{res.expected_points[i]:.1f}",
             *(f"{x:.3f}" for x in (res.p_top8[i], res.p_playoff[i], res.p_out[i],
                                    res.prob("r16")[i], res.prob("qf")[i], res.prob("sf")[i],
                                    res.prob("final")[i], res.prob("win")[i])))
            for i in order
        ],
    )  # fmt: skip

    with engine.begin() as conn:
        sim_id = write_results(conn, inputs, res, args.n, args.seed, sigma)
    print(f"simulation_runs id {sim_id}")
    with engine.connect() as conn:
        print_prob_diff(conn, names, elo, shrink)
    return 0 if all(abs(s - e) < 1e-9 for _, s, e in checks) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.simulate")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="simulate the rest of the season and store the results")
    run.add_argument("--n", type=int, default=10_000, help="number of simulations")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument(
        "--sigma", type=float, default=None,
        help="per-team rating noise in Elo points (default: estimated from earlier seasons of"
        " the same format; 0 = frozen ratings)",
    )  # fmt: skip
    run.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
