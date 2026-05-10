import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Config
from database.models import Base

logger = logging.getLogger(__name__)

def _normalize_db_url(url: str) -> str:
    """Adapt URL for asyncpg: enforce async driver, translate ssl param."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg uses `ssl=` instead of psycopg2's `sslmode=`
    if "+asyncpg" in url:
        url = url.replace("sslmode=require", "ssl=require")
        url = url.replace("sslmode=disable", "ssl=disable")
        url = url.replace("sslmode=verify-ca", "ssl=verify-ca")
        url = url.replace("sslmode=verify-full", "ssl=verify-full")
    return url


_db_url = _normalize_db_url(Config.DATABASE_URL)
_is_sqlite = _db_url.startswith("sqlite")

engine = create_async_engine(
    _db_url,
    echo=False,
    **({} if _is_sqlite else {"pool_size": 20, "max_overflow": 10, "pool_pre_ping": True}),
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")


async def close_db() -> None:
    """Close database engine."""
    await engine.dispose()
    logger.info("Database connection closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session with automatic commit/rollback."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
