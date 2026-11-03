from __future__ import annotations

import contextlib
import time

import structlog
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import BodySizeLimitMiddleware, RequestIdMiddleware, register_error_handlers
from backend.app.core.logging import configure_logging
from backend.app.db import engine as db_engine


def build_health_router(app: FastAPI) -> None:
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    async def ready() -> JSONResponse:
        start = time.perf_counter()
        checks: dict[str, str] = {}
        http_code = status.HTTP_200_OK
        try:
            session_factory = app.state.sessionmaker
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "fail"
            http_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        body = {"status": "ok" if http_code == 200 else "unavailable", "checks": checks, "take_ms": elapsed_ms}
        return JSONResponse(status_code=http_code, content=body)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    engine = db_engine.build_engine(settings)
    sessionmaker = db_engine.build_sessionmaker(engine)
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    yield
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Backend Infra",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1_000_000)
    app.add_middleware(RequestIdMiddleware)

    build_health_router(app)
    register_error_handlers(app)
    return app


app = create_app()
