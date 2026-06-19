"""Structured logging configuration and safe request-correlation helpers.

Logging uses ``structlog`` with an allowlist mindset: only non-sensitive, stable
metadata is ever bound to log records. Request bodies, headers, query values,
cookies, authorization material, connection strings, and raw exception text must
never be logged here. Configuration is idempotent so repeated application
construction (common in tests) does not change behavior or duplicate output.
"""

import logging
import re
from uuid import uuid4

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.typing import EventDict, Processor, WrappedLogger

from app.core.config import AppSettings

_LOG_LEVEL_NUMBERS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

# A conservative request-id policy: short, printable, URL/header-safe characters
# only. Anything outside this is replaced with a generated identifier so untrusted
# client input is never reflected into logs or response headers.
_REQUEST_ID_PATTERN = re.compile(r"\A[A-Za-z0-9._-]+\Z")


def _static_context_processor(service: str, environment: str) -> Processor:
    """Build a processor that stamps safe, constant service context on every event."""

    def processor(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", service)
        event_dict.setdefault("environment", environment)
        return event_dict

    return processor


def configure_logging(settings: AppSettings) -> None:
    """Configure structlog idempotently for the given settings.

    ``structlog.configure`` fully replaces the global configuration on every call,
    so invoking this repeatedly (for example, once per application factory in
    tests) neither accumulates handlers nor leaves stale processors behind.
    """

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _static_context_processor(settings.service_name, settings.environment),
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_LOG_LEVEL_NUMBERS[settings.log_level]),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given component name."""

    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger


def normalize_request_id(raw_value: str | None, *, max_length: int) -> str:
    """Return a safe request id, generating one when the input is missing/invalid.

    A client-supplied value is accepted only when it is non-empty, within
    ``max_length``, and matches the conservative character policy. Otherwise a new
    UUID-based identifier is generated so untrusted values are never trusted.
    """

    if raw_value is not None:
        candidate = raw_value.strip()
        if 0 < len(candidate) <= max_length and _REQUEST_ID_PATTERN.match(candidate):
            return candidate
    return uuid4().hex


def bind_request_context(**values: str) -> None:
    """Bind safe correlation values (such as ``request_id``) to the log context."""

    bind_contextvars(**values)


def clear_request_context() -> None:
    """Remove any request-scoped values from the log context."""

    clear_contextvars()
