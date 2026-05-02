"""Async PostgreSQL client using SQLAlchemy 2.0 + asyncpg."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings
from app.db.orm import Base

log = structlog.get_logger(__name__)
settings = get_settings()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_postgres() -> None:
    """Initialize the PostgreSQL connection pool and create all tables."""
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.postgres_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.app_env == "development",
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("postgres.initialized", url=settings.postgres_host)


async def close_postgres() -> None:
    if _engine:
        await _engine.dispose()
        log.info("postgres.closed")


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency-injectable async session context manager."""
    if _session_factory is None:
        raise RuntimeError("PostgreSQL not initialized. Call init_postgres() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
