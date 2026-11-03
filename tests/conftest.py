from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import httpx
import pytest_asyncio
from sqlalchemy import text

if sys.platform.startswith("win"):
    # psycopg async requires a Selector loop; Windows defaults to Proactor.
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_env_file(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


_VALUES = _load_env_file(ROOT / ".env")
TEST_DB_URL = _VALUES.get("TEST_DATABASE_URL", "")

# Every app instance inside tests uses the dedicated test database.
if TEST_DB_URL:
    os.environ["DATABASE_URL"] = TEST_DB_URL


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _migrate_test_db():
    """Apply migrations to the test database once per test session."""
    env = os.environ.copy()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT),
        env=env,
        check=True,
        capture_output=True,
    )
    yield


@pytest_asyncio.fixture
async def app_client():
    """App + httpx client wired to the test database; tables truncated after each test."""
    from backend.app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield app, client

    # Truncate all app tables between tests (fast, avoids shared-state leakage).
    engine = app.state.engine
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' "
                "AND tablename NOT LIKE 'alembic%' "
                "AND tablename NOT LIKE 'procrastinate%'"
            )
        )
        names = [r[0] for r in rows.fetchall()]
        if names:
            joined = ", ".join(f'"{n}"' for n in names)
            await conn.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
