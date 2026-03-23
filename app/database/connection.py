"""Async SQLAlchemy engine and session factory."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def _normalize_db_url(url: str) -> str:
    """Normalize DATABASE_URL to use asyncpg driver.

    Vercel Postgres / Supabase / Render issue urls as postgres:// or postgresql://
    but asyncpg requires the postgresql+asyncpg:// scheme.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _get_engine():
    global _engine
    if _engine is None and settings.DATABASE_URL:
        try:
            _engine = create_async_engine(
                _normalize_db_url(settings.DATABASE_URL),
                # NullPool is required for serverless environments (Vercel) where
                # persistent connection pools cannot be maintained across invocations.
                poolclass=NullPool,
                # statement_cache_size=0 disables asyncpg prepared statements,
                # required for compatibility with Supabase pgBouncer transaction mode.
                connect_args={"statement_cache_size": 0},
            )
        except Exception:
            logger.exception("Failed to create database engine")
    return _engine


async def init_tables() -> None:
    """Create all tables from ORM models if they don't exist."""
    from app.database.models import Base

    engine = _get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> tuple[bool, str]:
    """Test DB connectivity. Returns (is_ok, error_message)."""
    factory = _get_session_factory()
    if factory is None:
        return False, "DATABASE_URL not configured or engine creation failed"
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return True, ""
    except Exception as e:
        logger.exception("DB connection check failed")
        return False, str(e)


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        engine = _get_engine()
        if engine:
            _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async DB session."""
    factory = _get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with factory() as session:
        yield session


def is_db_available() -> bool:
    """Return True if DATABASE_URL is configured."""
    return bool(settings.DATABASE_URL)
