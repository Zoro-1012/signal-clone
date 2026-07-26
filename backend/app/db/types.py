"""Custom column types."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """A timestamp that is always timezone-aware UTC in Python.

    SQLite has no timezone-aware date type. ``DateTime(timezone=True)`` is
    accepted but does not round-trip: values come back *naive*, so comparing a
    stored expiry against an aware ``utcnow()`` raises
    ``TypeError: can't compare offset-naive and offset-aware datetimes`` — at
    runtime, in whichever code path happens to compare first, rather than
    anywhere near the model definition.

    Rather than scatter defensive ``.replace(tzinfo=...)`` calls across services,
    the conversion is enforced once, here:

    - on write, a naive value is assumed to be UTC and an aware value is converted
      to UTC, so the column is unambiguously UTC no matter what the caller passed;
    - on read, UTC is reattached, so every datetime leaving the database is aware.

    The database still stores a naive UTC timestamp, which keeps ordering and
    range queries working in plain SQL.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # A naive value from application code is UTC by convention; the app
            # never constructs local-time datetimes.
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):  # pragma: no cover - driver safety net
            raise TypeError(f"Expected a datetime from the database, got {type(value).__name__}")
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
