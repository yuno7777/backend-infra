from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.config import Settings


def build_engine(settings: Settings, url: str | None = None) -> AsyncEngine:
    return create_async_engine(
        url or settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": 5},
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_iterator(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
