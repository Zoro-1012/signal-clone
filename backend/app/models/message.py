"""Messages and everything attached to them: receipts, reactions, files."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UTCDateTime
from app.models.enums import MessageType, SystemEvent

if TYPE_CHECKING:  # pragma: no cover
    from app.models.conversation import Conversation
    from app.models.user import User


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single entry in a conversation transcript.

    Content is stored **only** as ciphertext. There is deliberately no plaintext
    column: keeping both would defeat the point of the sealing layer and make the
    encryption story dishonest. The cipher is simulated (see
    ``app.core.encryption``), but the storage shape is the one a real
    implementation needs, so nothing here would change if the mock were replaced.
    """

    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        # No index=True: ix_messages_conversation_created covers this column as
        # its leftmost prefix, so a standalone index would be pure write overhead.
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Null for system messages, which the server authors rather than a person.
    sender_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    type: Mapped[MessageType] = mapped_column(String(16), nullable=False, default=MessageType.TEXT)

    # --- Sealed content ---------------------------------------------------
    ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    encryption_key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encryption_algorithm: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- System messages --------------------------------------------------
    # Structured rather than a pre-rendered sentence, so wording stays a client
    # concern and can be translated or restyled without a migration.
    system_event: Mapped[SystemEvent | None] = mapped_column(String(48), nullable=True)
    system_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # --- Threading --------------------------------------------------------
    # Self-referential: a reply points at the message it quotes. SET NULL on
    # delete so removing the original degrades the quote instead of cascading
    # away every reply to it.
    reply_to_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- Idempotency ------------------------------------------------------
    # Client-generated identifier for the send. A retry after a timeout carries
    # the same value, so the unique constraint below turns a duplicate delivery
    # into a no-op rather than a second message. Essential on mobile networks,
    # where "did that send?" is the normal case.
    client_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Lifecycle --------------------------------------------------------
    # Set when a disappearing message is first delivered, not when it is created:
    # the timer should start once it can actually be read.
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    edited_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Soft delete, so the client can render a "this message was deleted" tombstone
    # and the surrounding receipt history stays intact.
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    # --- Relationships ----------------------------------------------------
    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
    sender: Mapped[User | None] = relationship(
        "User", back_populates="messages", foreign_keys=[sender_id]
    )
    reply_to: Mapped[Message | None] = relationship(
        "Message", remote_side="Message.id", foreign_keys=[reply_to_message_id]
    )
    receipts: Mapped[list[MessageReceipt]] = relationship(
        "MessageReceipt",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reactions: Mapped[list[MessageReaction]] = relationship(
        "MessageReaction",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # The single most important index in the schema: every transcript load is
        # "the newest N messages in this conversation", and pagination walks
        # backwards through it.
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        # Makes the retry-safety guarantee real rather than advisory. Scoped to the
        # sender so two people cannot collide on the same client-generated id.
        UniqueConstraint("sender_id", "client_message_id", name="uq_message_sender_client_id"),
        CheckConstraint("type IN ('text', 'media', 'system')", name="message_type_valid"),
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class MessageReceipt(UUIDPrimaryKeyMixin, Base):
    """One recipient's delivery and read state for one message.

    A row per recipient, rather than flags on the message, because in a group of
    seven the same message is delivered to everyone and read by three — a single
    pair of columns cannot express that. It also makes the single/double check UI
    a direct aggregate over these rows, and gives read receipts a natural place to
    be withheld per user if privacy settings were ever made real.

    No ``updated_at``: the two timestamps here *are* the history.
    """

    __tablename__ = "message_receipts"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Covered by ix_receipts_user_read as its leftmost prefix.
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    message: Mapped[Message] = relationship("Message", back_populates="receipts")
    user: Mapped[User] = relationship("User")

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_receipt_message_user"),
        # Supports "mark everything unread in this conversation as read" in one pass.
        Index("ix_receipts_user_read", "user_id", "read_at"),
    )


class MessageReaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An emoji reaction from one user to one message."""

    __tablename__ = "message_reactions"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    emoji: Mapped[str] = mapped_column(String(16), nullable=False)

    message: Mapped[Message] = relationship("Message", back_populates="reactions")
    user: Mapped[User] = relationship("User")

    __table_args__ = (
        # A person may react with several different emoji, but tapping the same one
        # twice is a toggle, never a duplicate.
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_reaction_message_user_emoji"),
    )


class Attachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A file or image carried by a message.

    Only metadata lives in the database; bytes live behind the storage interface
    in ``app.services.storage``. ``storage_key`` is an opaque handle rather than a
    URL or filesystem path, so moving from local disk to object storage needs no
    migration and no change to any row.
    """

    __tablename__ = "attachments"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # Separate derived image, so a thumbnail grid never downloads full-size originals.
    thumbnail_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Intrinsic dimensions, stored so the client can reserve the correct space
    # before the image loads and avoid the transcript jumping as media arrives.
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    message: Mapped[Message] = relationship("Message", back_populates="attachments")

    __table_args__ = (CheckConstraint("size_bytes >= 0", name="attachment_size_non_negative"),)
