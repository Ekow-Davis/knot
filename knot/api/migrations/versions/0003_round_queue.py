"""rounds: a queue of sealed questions, read_by

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24
"""

from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_suffix(".sql")


def statements(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";\n") if s.strip().rstrip(";")]


def upgrade() -> None:
    for stmt in statements(SQL.read_text(encoding="utf-8")):
        op.execute(stmt.rstrip(";"))


def downgrade() -> None:
    op.execute("DELETE FROM rounds")
    op.execute("ALTER TABLE rounds DROP COLUMN IF EXISTS read_by")
    op.execute("CREATE UNIQUE INDEX one_round_at_a_time ON rounds ((true))")
