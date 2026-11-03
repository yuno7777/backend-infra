from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from backend.app.core.config import get_settings
from backend.app.db.base import Base
from backend.app.db import engine as db_engine
import backend.app.models  # noqa: F401  (register all models with Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
MODELS = None  # import side effect only


def _sync_url() -> str:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = db_engine.build_engine(get_settings(), url=_sync_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    import asyncio
    import sys

    if sys.platform.startswith("win"):
        # psycopg async requires a Selector loop; Windows defaults to Proactor.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
