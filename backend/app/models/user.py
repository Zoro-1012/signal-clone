"""User identity and profile."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checking only
    from app.models.contact import Contact
    from app.models.conversation import ConversationParticipant
    from app.models.message import Message


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered account.

    Identity is the phone number, mirroring Signal. The username is a secondary,
    optional handle that makes the app usable in a demo where nobody wants to
    hand out a real number — both are unique and either can be used to find a
    person or to sign in.
    """

    __tablename__ = "users"

    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)

    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    about: Mapped[str | None] = mapped_column(String(140), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Deterministic fallback colour for the initials avatar shown when no image
    # is set. Persisted rather than derived at render time so a person keeps the
    # same colour everywhere, on every device, forever.
    avatar_color: Mapped[str] = mapped_column(String(16), nullable=False, default="ultramarine")

    # Presence. `is_online` reflects whether a live WebSocket connection exists and
    # is reset on shutdown; `last_seen_at` is the durable value shown when offline.
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Relationships ----------------------------------------------------
    # `passive_deletes` defers cascade to the database's ON DELETE rather than
    # having the ORM load every child row into memory just to delete it.
    contacts: Mapped[list[Contact]] = relationship(
        "Contact",
        foreign_keys="Contact.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    participations: Mapped[list[ConversationParticipant]] = relationship(
        "ConversationParticipant",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="sender",
        foreign_keys="Message.sender_id",
        passive_deletes=True,
    )

    __table_args__ = (
        # Presence sweeps and "who is online" lookups filter on this directly.
        Index("ix_users_is_online", "is_online"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.id} {self.display_name!r} {self.phone_number}>"
