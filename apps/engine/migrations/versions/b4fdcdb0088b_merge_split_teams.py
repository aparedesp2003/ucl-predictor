"""merge split teams

Revision ID: b4fdcdb0088b
Revises: 5c2e7a91d4b3
Create Date: 2026-11-08 03:46:55.000000

openfootball spells some clubs two ways; a spelling first seen before the football-data team
existed became a second team. This merges each duplicate into its canonical team:

- a pair is identified by the canonical team's ``fd_team_id`` and the duplicate's openfootball
  alias, never by ids (DEV and PROD ids differ);
- aliases and home/away matches move to the canonical team (``matches.updated_at = now()`` so the
  pipeline sees the change); every moved row is logged in ``team_merge_moves``;
- the duplicate row and its ``team_ratings`` stay (past model runs remain reproducible) and get
  ``merged_into_team_id``; predictions, model runs and simulation tables are not touched;
- a pair that is absent or already merged is skipped, so running it again is a no-op.

The logic is plain SQL so later changes to the engine code cannot alter what this migration does.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import Connection, text

# revision identifiers, used by Alembic.
revision: str = "b4fdcdb0088b"
down_revision: str | Sequence[str] | None = "5c2e7a91d4b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (canonical fd_team_id, duplicate's openfootball alias); found by the week-5 duplicate audit.
PAIRS: list[tuple[int, str]] = [
    (675, "Feyenoord"),  # Feyenoord Rotterdam
    (108, "Inter"),  # FC Internazionale Milano
    (498, "Sporting CP"),  # Sporting Clube de Portugal
]

# (table, team column) pairs a merge moves; updated_at is bumped on matches only.
_MOVED = (
    ("team_aliases", "team_id"),
    ("matches", "home_team_id"),
    ("matches", "away_team_id"),
)


def merge_pairs(conn: Connection, pairs: Sequence[tuple[int, str]]) -> dict[str, dict[str, int]]:
    """Merge each (fd_team_id, openfootball alias) pair; returns moved row counts per alias."""
    out = {}
    for fd_team_id, alias in pairs:
        canon = conn.execute(
            text("SELECT id, name, country FROM teams WHERE fd_team_id = :fd"), {"fd": fd_team_id}
        ).one_or_none()
        dup = conn.execute(
            text(
                "SELECT t.id, t.name, t.country, t.fd_team_id, t.merged_into_team_id"
                " FROM team_aliases a JOIN teams t ON t.id = a.team_id"
                " WHERE a.source = 'openfootball' AND a.alias = :alias"
            ),
            {"alias": alias},
        ).one_or_none()
        if canon is None or dup is None or dup.id == canon.id or dup.merged_into_team_id:
            continue  # pair not present here, or already merged

        what = f"{alias!r} (team {dup.id} {dup.name!r}) into fd {fd_team_id} ({canon.name!r})"
        if dup.fd_team_id is not None:
            raise RuntimeError(
                f"cannot merge {what}: the duplicate has fd_team_id {dup.fd_team_id}"
            )
        if dup.country and canon.country and dup.country != canon.country:
            raise RuntimeError(f"cannot merge {what}: countries {dup.country} != {canon.country}")
        both = conn.scalar(
            text(
                "SELECT count(*) FROM matches WHERE (home_team_id, away_team_id) IN"
                " ((:d, :c), (:c, :d))"
            ),
            {"d": dup.id, "c": canon.id},
        )
        if both:
            raise RuntimeError(f"cannot merge {what}: {both} matches have both teams")

        ids = {"d": dup.id, "c": canon.id}
        counts = {}
        for table, column in _MOVED:
            conn.execute(
                text(
                    "INSERT INTO team_merge_moves"
                    " (merged_team_id, into_team_id, table_name, column_name, row_id)"
                    f" SELECT :d, :c, '{table}', '{column}', id FROM {table} WHERE {column} = :d"
                ),
                ids,
            )
            bump = ", updated_at = now()" if table == "matches" else ""
            counts[f"{table}.{column}"] = conn.execute(
                text(f"UPDATE {table} SET {column} = :c{bump} WHERE {column} = :d"), ids
            ).rowcount
        conn.execute(text("UPDATE teams SET merged_into_team_id = :c WHERE id = :d"), ids)
        out[alias] = counts
    return out


def unmerge(conn: Connection, team_ids: Sequence[int] | None = None) -> list[int]:
    """Reverse merges (all, or of the given duplicate team ids) exactly, from the move log.

    Raises without changing anything if a merged team has no log, or if a logged row no longer
    exists or no longer points to the team it was moved to. Returns the unmerged team ids.
    """
    merged = conn.execute(
        text(
            "SELECT id, name, merged_into_team_id FROM teams WHERE merged_into_team_id IS NOT NULL"
            " AND (CAST(:ids AS int[]) IS NULL OR id = ANY(CAST(:ids AS int[]))) ORDER BY id"
        ),
        {"ids": list(team_ids) if team_ids is not None else None},
    ).all()

    plans, problems = [], []
    for team in merged:
        moves = conn.execute(
            text(
                "SELECT table_name, column_name, row_id, into_team_id FROM team_merge_moves"
                " WHERE merged_team_id = :t ORDER BY id"
            ),
            {"t": team.id},
        ).all()
        if not moves:
            problems.append(f"team {team.id} {team.name!r}: merged but no logged moves")
        for m in moves:
            if (m.table_name, m.column_name) not in _MOVED:
                problems.append(
                    f"team {team.id}: unexpected log entry {m.table_name}.{m.column_name}"
                )
                continue
            current = conn.scalar(
                text(f"SELECT {m.column_name} FROM {m.table_name} WHERE id = :r"), {"r": m.row_id}
            )
            if current != m.into_team_id:  # None: the row is gone
                problems.append(
                    f"team {team.id} {team.name!r}: {m.table_name}.{m.column_name} row {m.row_id}"
                    f" is {'gone' if current is None else f'now team {current}'},"
                    f" expected team {m.into_team_id}"
                )
        plans.append((team, moves))
    if problems:
        raise RuntimeError(
            "cannot reverse the team merge exactly; fix or remove these rows first:\n  "
            + "\n  ".join(problems)
        )

    for team, moves in plans:
        for table, column in _MOVED:
            rows = [m.row_id for m in moves if (m.table_name, m.column_name) == (table, column)]
            if rows:
                bump = ", updated_at = now()" if table == "matches" else ""
                conn.execute(
                    text(f"UPDATE {table} SET {column} = :t{bump} WHERE id = ANY(:rows)"),
                    {"t": team.id, "rows": rows},
                )
        conn.execute(
            text("UPDATE teams SET merged_into_team_id = NULL WHERE id = :t"), {"t": team.id}
        )
        conn.execute(text("DELETE FROM team_merge_moves WHERE merged_team_id = :t"), {"t": team.id})
    return [team.id for team, _ in plans]


def _require_online() -> None:
    if context.is_offline_mode():
        raise RuntimeError("merge_split_teams reads and moves rows; run it online, not with --sql")


def upgrade() -> None:
    """Upgrade schema."""
    _require_online()
    op.add_column("teams", sa.Column("merged_into_team_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_teams_merged_into_team_id_teams", "teams", "teams", ["merged_into_team_id"], ["id"]
    )
    op.create_check_constraint(
        op.f("ck_teams_not_merged_into_self"), "teams", "merged_into_team_id <> id"
    )
    op.create_table(
        "team_merge_moves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("merged_team_id", sa.Integer(), nullable=False),
        sa.Column("into_team_id", sa.Integer(), nullable=False),
        sa.Column("table_name", sa.String(length=32), nullable=False),
        sa.Column("column_name", sa.String(length=32), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),  # fmt: skip
        sa.ForeignKeyConstraint(
            ["merged_team_id"], ["teams.id"], name="fk_team_merge_moves_merged_team_id_teams"
        ),
        sa.ForeignKeyConstraint(
            ["into_team_id"], ["teams.id"], name="fk_team_merge_moves_into_team_id_teams"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_team_merge_moves"),
    )
    op.create_index("ix_team_merge_moves_merged_team_id", "team_merge_moves", ["merged_team_id"])

    for alias, counts in merge_pairs(op.get_bind(), PAIRS).items():
        print(f"merged {alias!r}: {counts}")


def downgrade() -> None:
    """Downgrade schema."""
    _require_online()
    for team_id in unmerge(op.get_bind()):
        print(f"unmerged team {team_id}")
    op.drop_index("ix_team_merge_moves_merged_team_id", table_name="team_merge_moves")
    op.drop_table("team_merge_moves")
    op.drop_constraint(op.f("ck_teams_not_merged_into_self"), "teams", type_="check")
    op.drop_constraint("fk_teams_merged_into_team_id_teams", "teams", type_="foreignkey")
    op.drop_column("teams", "merged_into_team_id")
