from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import get_settings

_s = get_settings()
engine = create_async_engine(
    _s.database_url,
    pool_pre_ping=True,
    **({"poolclass": NullPool} if _s.db_null_pool else {}),
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one database session per request."""
    async with SessionLocal() as session:
        yield session
