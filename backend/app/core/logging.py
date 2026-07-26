"""Logging setup.

Human-readable in development, JSON in production so a log aggregator can index
fields rather than regex lines. Configured once at startup; modules only ever
call ``get_logger``.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_CONFIGURED = False

# Attributes present on every LogRecord; anything else was added via `extra=`
# and therefore belongs in the structured output.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render records as single-line JSON, preserving ``extra`` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(*, debug: bool = False, json_output: bool = False) -> None:
    """Initialise root logging. Idempotent, so repeated app factories are safe."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if json_output
        else logging.Formatter(
            "%(asctime)s  %(levelname)-8s %(name)-34s %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Third-party libraries that log per-operation at DEBUG. Left unchecked,
    # aiosqlite alone emits two lines per statement and buries our own output.
    for noisy in (
        "sqlalchemy.engine",
        "aiosqlite",
        "uvicorn.access",
        "multipart",
        "httpx",
        "httpcore",
        "PIL",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
