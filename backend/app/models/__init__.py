"""ORM models.

Every model is imported here rather than lazily, for two reasons: SQLAlchemy
resolves the string-based relationship references between mappers only once all
of them are registered, and Alembic's autogenerate needs the complete metadata
from a single import to diff the schema correctly.
"""

from app.models.auth import RefreshToken, VerificationCode
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationParticipant
from app.models.enums import (
    ConversationType,
    MessageStatus,
    MessageType,
    ParticipantRole,
    SystemEvent,
)
from app.models.message import Attachment, Message, MessageReaction, MessageReceipt
from app.models.user import User

__all__ = [
    "Attachment",
    "Contact",
    "Conversation",
    "ConversationParticipant",
    "ConversationType",
    "Message",
    "MessageReaction",
    "MessageReceipt",
    "MessageStatus",
    "MessageType",
    "ParticipantRole",
    "RefreshToken",
    "SystemEvent",
    "User",
    "VerificationCode",
]
