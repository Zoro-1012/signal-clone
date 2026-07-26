"""Custom column types."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

from sqlalchemy import DateTime, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

E = TypeVar("E", bound=Enum)


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


class EnumString(TypeDecorator[E]):
    """Store an Enum by its value, and read it back as the Enum member.

    Declaring ``Mapped[MessageType] = mapped_column(String(16))`` type-checks and
    writes correctly — a ``str``-mixin enum binds as its value — but the column
    reads back as a plain ``str``. The annotation then lies: code that trusts it
    and calls ``.value`` crashes at runtime, and the only way to write safe code
    against it is defensive ``hasattr`` checks at every use site.

    This decorator makes the annotation true in both directions, so services can
    rely on enum members and exhaustive comparisons behave as written.

    Values, not names, are persisted: ``'text'`` is self-describing in a database
    console, whereas ``'TEXT'`` is an implementation detail of the Python class
    and would break if a member were ever renamed.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[E], length: int = 32) -> None:
        self.enum_class = enum_class
        super().__init__(length=length)

    def process_bind_param(self, value: E | str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return str(value.value)
        # Accept a raw string, but validate it: an unknown value would otherwise be
        # written happily and only fail later, on read, far from the cause.
        return str(self.enum_class(value).value)

    def process_result_value(self, value: Any, dialect: Dialect) -> E | None:
        if value is None:
            return None
        return self.enum_class(value)
