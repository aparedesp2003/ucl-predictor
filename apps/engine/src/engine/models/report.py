"""Console reports shared by the model and simulator CLIs."""

from collections.abc import Mapping

from sqlalchemy import Connection, select, text

from engine.cli import print_table
from engine.db.models import Match, MatchStatus
from engine.evaluate.candidates import compare_probs

Probs = tuple[float, float, float]


def official_scheduled(conn: Connection, model: str) -> dict[int, Probs]:
    """``model``'s official (pre-kick-off) predictions for matches still SCHEDULED."""
    rows = conn.execute(
        text(
            "SELECT o.match_id, o.p_home, o.p_draw, o.p_away FROM official_predictions o"
            " JOIN matches m ON m.id = o.match_id WHERE o.model = :model AND m.status = :status"
        ),
        {"model": model, "status": MatchStatus.SCHEDULED.value},
    )
    return {mid: (h, d, a) for mid, h, d, a in rows}


def print_prob_diff(
    conn: Connection,
    names: Mapping[int, str],
    a: Mapping[int, Probs],
    b: Mapping[int, Probs],
    labels: tuple[str, str] = ("elo", "poisson_shrink"),
    tol: float = 0.05,
) -> None:
    """Mean / max |a - b| over H/D/A of all matches both models predicted; list those > tol."""
    diff = compare_probs(a, b, tol)
    n = len(set(a) & set(b))
    print(
        f"\n{labels[0]} vs {labels[1]} on {n} scheduled matches: mean |diff| {diff.mean_abs:.4f},"
        f" max |diff| {diff.max_abs:.4f}, {len(diff.flagged)} matches differ by > {tol}"
    )
    if not diff.flagged:
        return
    teams = dict(
        (mid, (h, aw))
        for mid, h, aw in conn.execute(
            select(Match.id, Match.home_team_id, Match.away_team_id).where(
                Match.id.in_([i for i, _, _ in diff.flagged])
            )
        )
    )
    print_table(
        f"matches where {labels[0]} and {labels[1]} differ by > {tol}",
        ("home", "away", f"{labels[0]} H/D/A", f"{labels[1]} H/D/A", "max |diff|"),
        [
            (names[teams[i][0]], names[teams[i][1]], "/".join(f"{x:.3f}" for x in pa),
             "/".join(f"{x:.3f}" for x in pb), f"{abs(pa - pb).max():.3f}")
            for i, pa, pb in diff.flagged
        ],
    )  # fmt: skip
