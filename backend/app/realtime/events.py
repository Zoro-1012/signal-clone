"""The WebSocket event protocol.

Every frame is ``{"type": ..., "payload": {...}}``. The type strings are the
contract between backend and frontend, so they live in one enum rather than
being written as string literals at each send site — a typo in a literal fails
silently, as an event nobody listens for.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Every event that can cross the socket."""

    # Server -> client
    MESSAGE_NEW = "message.new"
    MESSAGE_UPDATED = "message.updated"
    MESSAGE_DELETED = "message.deleted"
    # Distinct from MESSAGE_DELETED on purpose. A deleted message leaves a
    # tombstone, because the other person saw it and hiding that it ever existed
    # would be dishonest. An expired message leaves nothing: the whole promise of
    # a disappearing message is that no trace remains.
    MESSAGE_EXPIRED = "message.expired"
    MESSAGE_STATUS = "message.status"
    REACTION_ADDED = "reaction.added"
    REACTION_REMOVED = "reaction.removed"
    CONVERSATION_UPDATED = "conversation.updated"
    PRESENCE_UPDATE = "presence.update"
    ERROR = "error"

    # Client -> server
    TYPING_START = "typing.start"
    TYPING_STOP = "typing.stop"
    PING = "ping"
    PONG = "pong"


def build(event: EventType, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble a frame in the shape both sides agree on."""
    return {"type": event.value, "payload": payload or {}}
