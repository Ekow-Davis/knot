"""The migration is hand-written SQL, so this test makes sure it never drifts from app/models.py.

Run against a migrated database:  alembic upgrade head && pytest
"""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.models import Base

pytestmark = pytest.mark.asyncio


def _diff(sync_conn):
    ctx = MigrationContext.configure(sync_conn, opts={"compare_type": True, "compare_server_default": False})
    return compare_metadata(ctx, Base.metadata)


async def test_models_match_migrated_database():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        diff = await conn.run_sync(_diff)
    await engine.dispose()
    # alembic_version is Alembic's own table; ignore it.
    diff = [d for d in diff if not (d[0] == "remove_table" and d[1].name == "alembic_version")]
    assert diff == [], f"models.py and the migration disagree:\n{diff}"
