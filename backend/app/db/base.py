"""Declarative base, naming conventions and shared model mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
    """Adds server-managed created/updated timestamps.

    Defaults are evaluated by the database, not Python, so rows written by
    migrations, the seeder or a direct SQL fix are timestamped consistently.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
