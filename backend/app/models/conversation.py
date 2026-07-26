"""Conversations and membership."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import EnumString, UTCDateTime
from app.models.enums import ConversationType, ParticipantRole

if TYPE_CHECKING:  # pragma: no cover
    from app.models.message import Message
    from app.models.user import User


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A thread, either one-to-one or a group.

    Both kinds share one table. A direct chat is simply a conversation with
    exactly two participants, which means one message pipeline, one permission
    check and one set of queries serve both — instead of two parallel
    implementations that drift apart the first time a feature is added.
    """

    __tablename__ = "conversations"

    type: Mapped[ConversationType] = mapped_column(EnumString(ConversationType, 16), nullable=False)

    # Groups are named and can carry an avatar. Direct conversations derive both
    # from the other participant, so these stay null.
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Canonical key for direct conversations: the two participant ids, sorted and
    # joined. A unique index on it makes "open a chat with this person" idempotent
    # at the database level, so two simultaneous taps cannot create two threads.
    # Null for groups, and SQLite's unique indexes ignore nulls, so groups are
    # unconstrained by it.
    direct_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)

    # Disappearing messages: seconds until a delivered message expires, or 0 for off.
    # Held on the conversation because in Signal the timer is a property of the
    # thread that every participant shares, not a per-message choice.
    disappearing_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Denormalised from the newest message. The conversation list sorts by this on
    # every load; without it each render would need a correlated subquery across
    # the whole message table. Written in the same transaction as the message, so
    # it cannot drift out of step.
    last_message_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    participants: Mapped[list[ConversationParticipant]] = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('direct', 'group')",
            name="conversation_type_valid",
        ),
        CheckConstraint(
            "disappearing_seconds >= 0",
            name="disappearing_seconds_non_negative",
        ),
        # Every conversation-list query is "my threads, newest first".
        Index("ix_conversations_last_message_at", "last_message_at"),
    )

    @property
    def is_group(self) -> bool:
        return self.type == ConversationType.GROUP

    @staticmethod
    def build_direct_key(user_id_a: str, user_id_b: str) -> str:
        """Return the order-independent key identifying a direct conversation.

        Sorting before joining is what makes it order-independent: A→B and B→A
        must produce the same key, or the uniqueness guarantee is worthless.
        """
        return ":".join(sorted((user_id_a, user_id_b)))


class ConversationParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Membership of a conversation, plus that member's private view of it.

    Per-user state lives here rather than on the conversation because muting,
    pinning and read position are personal: two members of the same group hold
    different values simultaneously.
    """

    __tablename__ = "conversation_participants"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Covered by ix_participants_user_conversation as its leftmost prefix.
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[ParticipantRole] = mapped_column(
        EnumString(ParticipantRole, 16), nullable=False, default=ParticipantRole.MEMBER
    )

    joined_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
    # Set instead of deleting the row, so historical messages keep a resolvable
    # sender and the transcript does not develop holes when someone leaves.
    left_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    # Read watermark: the newest message this member has read. Unread count is
    # derived from it. A stored counter would be denormalised state that drifts
    # under concurrent reads; a watermark is idempotent — applying it twice is
    # identical to applying it once — and self-corrects.
    last_read_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    is_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="participants")
    user: Mapped[User] = relationship("User", back_populates="participations")

    __table_args__ = (
        # One membership row per person per conversation.
        UniqueConstraint("conversation_id", "user_id", name="uq_participant_conversation_user"),
        CheckConstraint("role IN ('member', 'admin')", name="participant_role_valid"),
        # Serves the hot path: "list every conversation this user belongs to".
        Index("ix_participants_user_conversation", "user_id", "conversation_id"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == ParticipantRole.ADMIN

    @property
    def is_active(self) -> bool:
        return self.left_at is None
