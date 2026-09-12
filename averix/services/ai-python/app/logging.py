"""Structured logging, with the same redaction guarantee the Go service has."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

# Keys whose values must never reach a log line, whatever a caller passes.
# Cheaper to enforce once here than to audit every call site.
_SECRET_KEYS = frozenset(
    {
        "token",
        "service_token",
        "api_key",
        "anthropic_api_key",
        "access_token",
        "refresh_token",
        "authorization",
        "password",
        "secret",
        "cookie",
    }
)


def _redact(_logger: Any, _name: str, event: dict[str, Any]) -> dict[str, Any]:
    for key in list(event):
        if key.lower() in _SECRET_KEYS:
            event[key] = "[redacted]"
    return event


def configure(level: str = "info", json_output: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "averix-ai") -> structlog.BoundLogger:
    return structlog.get_logger(name)
