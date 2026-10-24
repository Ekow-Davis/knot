"""rounds: ready state, pulled_by, one round at a time

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24
"""

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
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
    op.execute("DROP INDEX IF EXISTS one_round_at_a_time")
    op.execute("ALTER TABLE rounds DROP COLUMN IF EXISTS pulled_by")
    op.execute("DELETE FROM rounds")
    op.execute("ALTER TABLE rounds DROP CONSTRAINT round_state")
    op.execute("ALTER TABLE rounds ADD CONSTRAINT round_state CHECK (state IN ('open', 'revealed', 'verdict'))")
