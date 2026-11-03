from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class AppError(Exception):
    """Base for every known, contract-defined error."""

    def __init__(self, code: str, message: str, status_code: int, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class UnauthenticatedError(AppError):
    def __init__(self, message: str = "Authentication required."):
        super().__init__("unauthenticated", message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Not permitted for this resource."):
        super().__init__("forbidden", message, status.HTTP_403_FORBIDDEN)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found."):
        super().__init__("not_found", message, status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, retry_after: int | None = None):
        super().__init__(code, message, status.HTTP_409_CONFLICT)
        self.retry_after = retry_after


class InvalidStateError(AppError):
    def __init__(self, message: str):
        super().__init__("invalid_state", message, status.HTTP_409_CONFLICT)


class RateLimitedError(AppError):
    def __init__(self, retry_after: int):
        super().__init__("rate_limited", "Rate limit exceeded.", status.HTTP_429_TOO_MANY_REQUESTS, details=[{"retry_after": retry_after}])
        self.retry_after = retry_after


class InternalError(AppError):
    def __init__(self, message: str = "Internal error."):
        super().__init__("internal_error", message, status.HTTP_500_INTERNAL_SERVER_ERROR)


def error_response(request: Request, err: AppError, headers: dict[str, str] | None = None) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "") or ""
    body = {
        "error": {"code": err.code, "message": err.message, "details": err.details},
        "request_id": request_id,
    }
    return JSONResponse(status_code=err.status_code, content=body, headers=headers)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign (or accept) an X-Request-ID, bind it to logs, return it in responses."""

    async def dispatch(self, request: Request, call_next):
        raw = request.headers.get("x-request-id", "")
        request_id = raw if raw and 8 <= len(raw) <= 64 else uuid.uuid4().hex
        request.state.request_id = request_id
        import structlog

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        headers: dict[str, str] = {}
        if getattr(exc, "retry_after", None) is not None:
            headers["Retry-After"] = str(exc.retry_after)
        return error_response(request, exc, headers or None)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        default_codes = {
            status.HTTP_401_UNAUTHORIZED: "unauthenticated",
            status.HTTP_403_FORBIDDEN: "forbidden",
            status.HTTP_404_NOT_FOUND: "not_found",
            status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
            status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
        }
        code = default_codes.get(exc.status_code, "http_error")
        err = AppError(code, str(exc.detail), exc.status_code)
        return error_response(request, err)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = jsonable_encoder(exc.errors(), custom_encoder={})
        err = AppError("validation_error", "Request validation failed.", status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)
        return error_response(request, err)

    @app.exception_handler(status.HTTP_413_CONTENT_TOO_LARGE)
    async def _entity_too_large(request: Request, exc):
        return error_response(request, AppError("payload_too_large", "Request body too large.", 413))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        import structlog

        structlog.get_logger(__name__).error("unhandled_exception", exc_info=True)
        return error_response(request, InternalError())


class BodySizeLimitMiddleware:
    """Reject oversized bodies early with 413 instead of buffering them."""

    def __init__(self, app: ASGIApp, max_bytes: int = 1_000_000):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        content_length = 0
        for key, value in scope.get("headers", []):
            if key == b"content-length":
                content_length = int(value.decode("ascii", "ignore"))
                break
        if content_length > self.max_bytes:
            request = Request(scope)
            request.state.request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
            response = error_response(
                request,
                AppError("payload_too_large", "Request body too large.", status.HTTP_413_CONTENT_TOO_LARGE),
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
