from __future__ import annotations

from backend.app.core.config import Settings


async def test_health_liveness(app_client):
    _app, client = app_client
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_request_id_is_returned_and_stable(app_client):
    _app, client = app_client
    response = await client.get("/health", headers={"X-Request-ID": "test-request-id-1234"})
    assert response.headers["X-Request-ID"] == "test-request-id-1234"

    response2 = await client.get("/health")
    assert len(response2.headers["X-Request-ID"]) >= 8


async def test_ready_ok_with_database(app_client):
    _app, client = app_client
    response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


async def test_ready_503_when_database_unreachable():
    from backend.app.main import create_app

    import httpx

    dead_settings = Settings(database_url="postgresql+psycopg://backend_infra:x@127.0.0.1:59999/backend_infra")
    app = create_app(settings=dead_settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/ready")
            assert response.status_code == 503
            body = response.json()
            assert body["status"] == "unavailable"
            assert body["checks"]["database"] == "fail"


async def test_error_envelope_shape(app_client):
    """Unknown route 404 uses the documented error envelope with request_id."""
    _app, client = app_client
    response = await client.get("/definitely-not-a-route")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert len(body["request_id"]) >= 8


async def test_payload_too_large_rejected(app_client):
    _app, client = app_client
    response = await client.post(
        "/definitely-not-a-route",
        content=b"x" * 1_500_000,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
