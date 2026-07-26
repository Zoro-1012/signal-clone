"""Declarative base, naming conventions and shared model mixins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import UTCDateTime


def _utcnow() -> datetime:
    """Timezone-aware now, with the microsecond precision SQLite lacks."""
    return datetime.now(timezone.utc)


# Explicit constraint naming. Without this SQLite generates anonymous constraints,
# and Alembic then cannot emit a DROP for them — migrations become one-way.
# Naming them up front keeps every migration reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Common declarative base for every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_uuid() -> str:
    """Generate a primary key.

    UUIDs rather than autoincrementing integers: identifiers appear in URLs and
    WebSocket payloads, and sequential integers would leak volume (how many users
    exist, how many messages were sent) and allow trivial enumeration of other
    people's resources. Stored as a 32-char hex string because SQLite has no
    native UUID type.
    """
    return uuid.uuid4().hex


class UUIDPrimaryKeyMixin:
    """Adds a client-unguessable string primary key.

    No ``index=True``: SQLite already maintains an implicit index for a non-INTEGER
    primary key, so declaring one would build a second identical B-tree that every
    insert has to update for no read benefit.
    """

    id: Mapped[str] = mapped_column(primary_key=True, default=new_uuid)


class TimestampMixin:
    """Adds created/updated timestamps with microsecond precision.

    The default is generated in Python, not by the database. SQLite's
    ``CURRENT_TIMESTAMP`` resolves only to the **second**, so every message sent
    within the same second would share a timestamp — and since the tie-break is a
    random UUID, a transcript would render those messages in arbitrary order.
    For a chat application that is a correctness bug, not a cosmetic one: it also
    breaks cursor pagination, which relies on a total order.

    ``server_default`` is kept as a safety net so a row inserted by raw SQL or a
    migration still gets a timestamp, just a coarser one.
    """

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
