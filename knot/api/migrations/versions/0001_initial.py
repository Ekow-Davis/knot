"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).with_suffix(".sql")

TABLES = [
    "push_subscriptions",
    "sealed_answers",
    "rounds",
    "drawn_questions",
    "questions",
    "question_packs",
    "invites",
    "sessions",
    "email_codes",
    "pair",
    "users",
]


def statements(sql: str) -> list[str]:
    """asyncpg runs one statement per call, so split the file on ';' at end of line.
    (Safe here: no statement contains ';' inside a string.)"""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";\n") if s.strip().rstrip(";")]


def upgrade() -> None:
    for stmt in statements(SQL.read_text(encoding="utf-8")):
        op.execute(stmt.rstrip(";"))


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
