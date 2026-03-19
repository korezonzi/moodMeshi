"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

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
        _engine = create_async_engine(
            _normalize_db_url(settings.DATABASE_URL),
            # NullPool is required for serverless environments (Vercel) where
            # persistent connection pools cannot be maintained across invocations.
            poolclass=NullPool,
        )
    return _engine


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
