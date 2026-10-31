"""predictions.created_at and model_runs.created_at must come from the database clock (now()).

The official_predictions view compares created_at with kick-off, so a Python-side timestamp (wrong
clock, wrong time zone, a stale ``now`` captured early) could make a late prediction look pre-match.
"""

import ast
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import Insert, Select

from engine.db.models import ModelRunKind
from engine.models.store import create_model_run, write_predictions

SRC = Path(__file__).resolve().parents[1] / "src" / "engine"
GUARDED_TABLES = {"predictions", "model_runs"}


class RecordingConn:
    """Just enough of a Connection for create_model_run / write_predictions."""

    def __init__(self) -> None:
        self.inserts: list[Insert] = []

    def scalar(self, stmt):
        self.inserts.append(stmt)
        return 1

    def execute(self, stmt, *args):
        if isinstance(stmt, Insert):
            self.inserts.append(stmt)
            return []
        assert isinstance(stmt, Select)
        cols = [c.name for c in stmt.selected_columns]
        if cols == ["id", "kickoff_utc", "match_date"]:
            return [(10, datetime(2100, 1, 1, tzinfo=UTC), date(2100, 1, 1))]
        return []  # no existing predictions


def _compiled(stmt: Insert):
    return stmt.compile(dialect=postgresql.dialect())


def test_writers_never_bind_created_at():
    conn = RecordingConn()
    run_id = create_model_run(conn, ModelRunKind.PREDICT, {}, None, None, model="x")
    write_predictions(conn, run_id, {10: (0.5, 0.3, 0.2)}, datetime(2099, 1, 1, tzinfo=UTC))

    tables = {s.table.name for s in conn.inserts}
    assert tables == GUARDED_TABLES
    for stmt in conn.inserts:
        compiled = _compiled(stmt)
        assert not [k for k in compiled.params if k.startswith("created_at")], str(compiled)
        sql = str(compiled)
        if "ON CONFLICT" in sql:  # a re-predicted row gets the server's now(), never a bind
            assert "created_at = now()" in sql


def _is_func_now(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "now"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "func"
    )


def test_no_source_assigns_created_at_from_python():
    offenders = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "created_at":
                values = [node.value]
            elif isinstance(node, ast.Dict):
                values = [
                    v
                    for k, v in zip(node.keys, node.values, strict=True)
                    if isinstance(k, ast.Constant) and k.value == "created_at"
                ]
            else:
                continue
            offenders += [
                f"{path.relative_to(SRC)}:{v.lineno}" for v in values if not _is_func_now(v)
            ]
    assert offenders == []
