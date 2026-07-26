"""Message schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.models.enums import MessageStatus, MessageType
from app.schemas.common import APIModel
from app.schemas.user import UserPublic

MAX_MESSAGE_LENGTH = 4096


class AttachmentRead(APIModel):
    """A file carried by a message. URLs are built from the opaque storage key."""

    id: str
    file_name: str
    content_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    url: str
    thumbnail_url: str | None = None


class ReactionSummary(APIModel):
    """Reactions of one emoji, aggregated for display.

    Sending every individual reaction row would make a popular message expensive
    to render; the client needs the emoji, the count, who reacted, and whether
    the viewer is among them.
    """

    emoji: str
    count: int
    user_ids: list[str]
    reacted_by_me: bool = False


class QuotedMessage(APIModel):
    """The compact form of a message being replied to.

    A snapshot rather than a nested MessageRead: replies would otherwise nest
    recursively down a long chain, and a quote only ever renders one line.
    """

    id: str
    sender_id: str | None
    sender_display_name: str | None
    preview: str
    type: MessageType
    is_deleted: bool = False


class MessageRead(APIModel):
    """A message as the client renders it."""

    id: str
    conversation_id: str
    sender: UserPublic | None
    type: MessageType

    body: str | None = None
    created_at: datetime
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    expires_at: datetime | None = None

    reply_to: QuotedMessage | None = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    reactions: list[ReactionSummary] = Field(default_factory=list)

    # Structured system events, rendered client-side (see PROJECT.md §4).
    system_event: str | None = None
    system_meta: dict[str, Any] | None = None

    # Echoed back so an optimistic local message can be reconciled with the
    # server's copy instead of appearing twice.
    client_message_id: str | None = None

    # Derived from receipt rows, not stored: in a group the same message is
    # delivered to everyone and read by only some.
    status: MessageStatus = MessageStatus.SENT
    delivered_count: int = 0
    read_count: int = 0
    recipient_count: int = 0


class MessageCreate(APIModel):
    """Send a message."""

    body: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)
    reply_to_message_id: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)

    # Client-generated, so a retry after a network timeout is recognised as the
    # same send rather than creating a second message.
    client_message_id: str | None = Field(default=None, max_length=64)

    @field_validator("body")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MessageUpdate(APIModel):
    """Edit a message's text."""

    body: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("body")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("A message cannot be empty.")
        return stripped


class ReactionCreate(APIModel):
    """Add an emoji reaction."""

    emoji: str = Field(..., min_length=1, max_length=16)


class TypingSignal(APIModel):
    """Signal that the caller is or is not composing."""

    is_typing: bool = True
