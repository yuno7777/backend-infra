from __future__ import annotations

import logging

import structlog

from backend.app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging once per process."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _redact,
    ]

    renderer: structlog.typing.Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Keys whose values must never appear in logs.
_REDACT_KEYS = {
    "password",
    "token",
    "secret",
    "signature",
    "authorization",
    "api_key",
    "api-key",
    "session_token",
    "webhook_secret",
}


def _redact(
    _logger: structlog.typing.AnyLogger,
    _name: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.EventDict:
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict
