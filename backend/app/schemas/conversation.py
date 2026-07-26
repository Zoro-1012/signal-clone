"""Conversation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.models.enums import ConversationType, ParticipantRole
from app.schemas.common import APIModel
from app.schemas.user import UserPublic


class ParticipantRead(APIModel):
    """A member of a conversation, with their role and membership state."""

    user: UserPublic
    role: ParticipantRole
    joined_at: datetime
    left_at: datetime | None = None


class LastMessagePreview(APIModel):
    """The one-line summary shown against a conversation in the list.

    Content is decrypted and truncated server-side. Sending the whole message
    just to render 40 characters would waste bandwidth on every conversation in
    the list, on every load.
    """

    id: str
    sender_id: str | None
    sender_display_name: str | None
    preview: str
    type: str
    created_at: datetime
    is_deleted: bool = False

    # System messages carry their event and metadata instead of prose, so the
    # client renders the wording. Keeping that consistent between the transcript
    # and the list preview avoids two different phrasings of the same event.
    system_event: str | None = None
    system_meta: dict[str, object] | None = None


class ConversationRead(APIModel):
    """A conversation as it appears in the list or the chat header."""

    id: str
    type: ConversationType
    name: str | None
    avatar_url: str | None
    avatar_color: str | None = None
    disappearing_seconds: int
    created_at: datetime
    last_message_at: datetime | None

    participants: list[ParticipantRead]
    last_message: LastMessagePreview | None = None

    # Per-viewer state. Two members of the same group see different values here,
    # which is why it belongs on the response rather than on the stored conversation.
    unread_count: int = 0
    is_muted: bool = False
    is_pinned: bool = False
    my_role: ParticipantRole = ParticipantRole.MEMBER


class DirectConversationCreate(APIModel):
    """Open (or reopen) a one-to-one conversation."""

    user_id: str


class GroupConversationCreate(APIModel):
    """Create a named group."""

    name: str = Field(..., min_length=1, max_length=128)
    member_ids: list[str] = Field(default_factory=list, max_length=256)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("A group needs a name.")
        return stripped

    @field_validator("member_ids")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        """Collapse repeats.

        The client can send the same id twice through double-tap or a stale list;
        that should be a harmless no-op, not a unique-constraint violation.
        """
        return list(dict.fromkeys(value))


class ConversationUpdate(APIModel):
    """Change group metadata, or the shared disappearing-message timer."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=512)
    disappearing_seconds: int | None = Field(default=None, ge=0, le=60 * 60 * 24 * 7)

    @model_validator(mode="after")
    def _require_a_change(self) -> ConversationUpdate:
        if self.name is None and self.avatar_url is None and self.disappearing_seconds is None:
            raise ValueError("Provide at least one field to update.")
        return self


class ParticipantsAdd(APIModel):
    """Add members to a group."""

    user_ids: list[str] = Field(..., min_length=1, max_length=128)

    @field_validator("user_ids")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class MarkReadRequest(APIModel):
    """Advance the caller's read watermark."""

    message_id: str
