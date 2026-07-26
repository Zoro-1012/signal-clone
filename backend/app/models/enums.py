"""Enumerations shared by the ORM models and the API schemas.

Stored as strings rather than integers: a row that reads ``type='group'`` is
self-describing in a database console, and adding a member later never risks
renumbering an existing one.
"""

from __future__ import annotations

from enum import Enum


class ConversationType(str, Enum):
    """A conversation is either between exactly two people, or a named group."""

    DIRECT = "direct"
    GROUP = "group"


class ParticipantRole(str, Enum):
    """Group authority. Direct conversations treat everyone as a member."""

    MEMBER = "member"
    ADMIN = "admin"


class MessageType(str, Enum):
    """What a message row represents.

    ``SYSTEM`` covers events the transcript should show but no user typed —
    someone joined, the group was renamed, the disappearing timer changed.
    Modelling them as messages keeps the timeline a single ordered sequence
    instead of forcing the client to merge two streams.
    """

    TEXT = "text"
    MEDIA = "media"
    SYSTEM = "system"


class SystemEvent(str, Enum):
    """The specific occurrence behind a ``SYSTEM`` message.

    Stored as an event plus JSON metadata rather than a pre-rendered sentence,
    so the client owns the wording — which keeps translation and formatting a
    presentation concern rather than something frozen into the database.
    """

    GROUP_CREATED = "group_created"
    MEMBERS_ADDED = "members_added"
    MEMBER_REMOVED = "member_removed"
    MEMBER_LEFT = "member_left"
    GROUP_RENAMED = "group_renamed"
    GROUP_AVATAR_CHANGED = "group_avatar_changed"
    ROLE_CHANGED = "role_changed"
    DISAPPEARING_TIMER_CHANGED = "disappearing_timer_changed"


class MessageStatus(str, Enum):
    """Delivery lifecycle as presented in the UI.

    Derived from receipt rows rather than stored on the message: in a group the
    same message is simultaneously read by one member and merely delivered to
    another, so a single column could not represent the truth. ``SENDING`` is
    client-side only — it describes a message the server has not yet acknowledged.
    """

    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
