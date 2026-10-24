"""Test setup. Uses a separate database (knot_test) so your dev data is never touched.

One-time:  in psql, run  CREATE DATABASE knot_test OWNER knot;
Override:  set TEST_DATABASE_URL if yours lives somewhere else.
"""

import os

# These must be set before anything from `app` is imported (settings are read once).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:B.r.y.%40.n2005@localhost:5432/knot_test"
)
os.environ["DB_NULL_POOL"] = "true"
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-1234567890"
os.environ["OWNER_EMAIL"] = "baron@example.com"
os.environ["RESEND_API_KEY"] = ""
os.environ["BANK_KEY"] = "dGVzdC1iYW5rLWtleS0zMi1ieXRlcy1sb25nISEhISE="  # 32 bytes, tests only

from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import deps  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.live import hub  # noqa: E402
from app.main import app  # noqa: E402
from app.routes import auth as auth_routes  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the test database from the real migrations, from scratch, once per run."""
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


TABLES = (
    "push_subscriptions, sealed_answers, rounds, drawn_questions, questions, question_packs, "
    "invites, sessions, email_codes, pair, users"
)


@pytest.fixture(autouse=True)
async def clean():
    """Every test starts with empty tables and fresh rate limits."""
    async with SessionLocal() as db:
        await db.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await db.commit()
    for limiter in (
        deps.code_requests_per_ip,
        deps.verify_attempts_per_ip,
        deps.pair_attempts_per_ip,
        deps.pair_attempts_per_ticket,
    ):
        limiter.reset()
    hub.reset()


@pytest.fixture
async def bank():
    """The throwaway test pack (sample/test-000.json), imported the same way the real bank is."""
    from app.tools.import_pack import import_pack

    assert await import_pack(API_DIR / "sample" / "test-000.json") == 0


@pytest.fixture
def outbox(monkeypatch):
    """Captures sign-in emails instead of sending them: {email: [code, code, ...]}."""
    sent: dict[str, list[str]] = defaultdict(list)

    async def fake_send(to: str, code: str) -> None:
        sent[to].append(code)

    monkeypatch.setattr(auth_routes, "send_code", fake_send)
    return sent


@pytest.fixture
def make_client():
    """Each client is one phone, with its own cookie jar."""
    clients: list[httpx.AsyncClient] = []

    def _make() -> httpx.AsyncClient:
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        return c

    yield _make
    # Clients hold no real sockets with ASGITransport; nothing to close.
