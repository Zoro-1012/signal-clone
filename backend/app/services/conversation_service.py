"""Conversation and membership rules.

Owns authorisation for everything conversation-scoped. The rule is uniform:
access requires an active membership row, and group administration additionally
requires the admin role. Both are checked here rather than in routers, so no
endpoint can forget.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import Envelope, cipher
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import utcnow
from app.models.conversation import Conversation, ConversationParticipant
from app.models.enums import ConversationType, MessageType, ParticipantRole, SystemEvent
from app.models.message import Message
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.conversation import (
    ConversationRead,
    ConversationUpdate,
    LastMessagePreview,
    ParticipantRead,
)
from app.schemas.user import UserPublic

logger = get_logger(__name__)

PREVIEW_LENGTH = 120


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.users = UserRepository(session)

    # -- Authorisation -----------------------------------------------------

    async def require_participation(
        self, conversation_id: str, user: User
    ) -> ConversationParticipant:
        """Assert the caller is an active member, and return their membership.

        Raises NotFound rather than Forbidden for a conversation the caller is not
        in: telling them it exists would leak the existence of other people's
        conversations to anyone willing to guess identifiers.
        """
        participation = await self.conversations.get_participation(conversation_id, user.id)
        if participation is None:
            raise NotFoundError("That conversation does not exist.")
        return participation

    async def require_admin(self, conversation_id: str, user: User) -> ConversationParticipant:
        participation = await self.require_participation(conversation_id, user)
        conversation = await self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("That conversation does not exist.")
        # Direct conversations have no hierarchy; both people are equals.
        if conversation.is_group and not participation.is_admin:
            raise PermissionDeniedError("Only group admins can do that.")
        return participation

    # -- Reading -----------------------------------------------------------

    async def list_conversations(
        self, user: User, *, query: str | None = None
    ) -> list[ConversationRead]:
        """Build the conversation list in a fixed number of queries.

        Four round trips total, whatever the number of conversations: the
        conversations themselves, their members, their newest message, and the
        unread counts. Assembling in Python keeps the cost flat instead of
        growing with the list.
        """
        conversations = await self.conversations.list_for_user(user.id, query=query)
        if not conversations:
            return []

        ids = [conversation.id for conversation in conversations]
        participants = await self.conversations.list_participants(ids, include_left=False)
        latest = await self.conversations.latest_messages(ids)
        unread = await self.conversations.unread_counts(user.id, ids)

        my_participation = {
            conversation.id: next(
                (p for p in participants.get(conversation.id, []) if p.user_id == user.id),
                None,
            )
            for conversation in conversations
        }

        return [
            self._assemble(
                conversation,
                viewer=user,
                participants=participants.get(conversation.id, []),
                mine=my_participation[conversation.id],
                last_message=latest.get(conversation.id),
                unread_count=unread.get(conversation.id, 0),
            )
            for conversation in conversations
        ]

    async def get_conversation(self, user: User, conversation_id: str) -> ConversationRead:
        await self.require_participation(conversation_id, user)
        conversation = await self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("That conversation does not exist.")

        participants = (await self.conversations.list_participants([conversation_id]))[
            conversation_id
        ]
        latest = await self.conversations.latest_messages([conversation_id])
        unread = await self.conversations.unread_counts(user.id, [conversation_id])
        mine = next((p for p in participants if p.user_id == user.id), None)

        return self._assemble(
            conversation,
            viewer=user,
            participants=[p for p in participants if p.left_at is None],
            mine=mine,
            last_message=latest.get(conversation_id),
            unread_count=unread.get(conversation_id, 0),
        )

    def _assemble(
        self,
        conversation: Conversation,
        *,
        viewer: User,
        participants: list[ConversationParticipant],
        mine: ConversationParticipant | None,
        last_message: Message | None,
        unread_count: int,
    ) -> ConversationRead:
        """Project stored rows into the shape a single viewer needs.

        A direct conversation has no stored name or avatar — it is presented as
        the other person. Resolving that here means the client never has to know
        the difference between a group and a one-to-one chat when rendering a row.
        """
        name = conversation.name
        avatar_url = conversation.avatar_url
        avatar_color: str | None = None

        if conversation.type == ConversationType.DIRECT:
            other = next((p.user for p in participants if p.user_id != viewer.id), None)
            # A conversation with yourself (Note to Self) legitimately has no other.
            subject = other or viewer
            name = subject.display_name
            avatar_url = subject.avatar_url
            avatar_color = subject.avatar_color

        return ConversationRead(
            id=conversation.id,
            type=conversation.type,
            name=name,
            avatar_url=avatar_url,
            avatar_color=avatar_color,
            disappearing_seconds=conversation.disappearing_seconds,
            created_at=conversation.created_at,
            last_message_at=conversation.last_message_at,
            participants=[
                ParticipantRead(
                    user=UserPublic.model_validate(participant.user),
                    role=participant.role,
                    joined_at=participant.joined_at,
                    left_at=participant.left_at,
                )
                for participant in participants
            ],
            last_message=self._preview(last_message),
            unread_count=unread_count,
            is_muted=mine.is_muted if mine else False,
            is_pinned=mine.is_pinned if mine else False,
            my_role=mine.role if mine else ParticipantRole.MEMBER,
        )

    @staticmethod
    def _preview(message: Message | None) -> LastMessagePreview | None:
        """Summarise a message for the list, decrypting only what is displayed."""
        if message is None:
            return None

        preview = ""
        if message.type == MessageType.TEXT and message.ciphertext:
            plaintext = cipher.open(
                Envelope(
                    ciphertext=message.ciphertext,
                    key_id=message.encryption_key_id or "",
                    algorithm=message.encryption_algorithm or "",
                )
            )
            preview = plaintext[:PREVIEW_LENGTH]
        elif message.type == MessageType.MEDIA:
            preview = "Attachment"

        return LastMessagePreview(
            id=message.id,
            sender_id=message.sender_id,
            sender_display_name=message.sender.display_name if message.sender else None,
            preview=preview,
            type=message.type.value,
            created_at=message.created_at,
            is_deleted=message.deleted_at is not None,
            system_event=message.system_event.value if message.system_event else None,
            system_meta=message.system_meta,
        )

    # -- Creating ----------------------------------------------------------

    async def create_direct(self, user: User, other_user_id: str) -> Conversation:
        """Open a one-to-one conversation, reusing the existing one if there is one.

        Idempotent by design: tapping a contact twice must land in the same
        thread, not create a second one. The canonical direct_key and its unique
        index enforce that even when two requests race.
        """
        other = await self.users.get(other_user_id)
        if other is None or not other.is_active:
            raise NotFoundError("That person is not available.")

        existing = await self.conversations.get_direct(user.id, other.id)
        if existing is not None:
            return existing

        conversation = Conversation(
            type=ConversationType.DIRECT,
            created_by=user.id,
            direct_key=Conversation.build_direct_key(user.id, other.id),
        )
        self.conversations.add(conversation)
        await self.session.flush()

        self.session.add_all(
            [
                ConversationParticipant(conversation_id=conversation.id, user_id=user.id),
                ConversationParticipant(conversation_id=conversation.id, user_id=other.id),
            ]
        )
        await self.session.commit()
        return conversation

    async def create_group(self, user: User, *, name: str, member_ids: list[str]) -> Conversation:
        """Create a group with the caller as its first admin."""
        wanted = [uid for uid in member_ids if uid != user.id]
        members = await self.users.list_by_ids(wanted)
        if len(members) != len(wanted):
            raise ValidationError("One or more of those people could not be found.")

        conversation = Conversation(
            type=ConversationType.GROUP,
            name=name,
            created_by=user.id,
        )
        self.conversations.add(conversation)
        await self.session.flush()

        self.session.add(
            ConversationParticipant(
                conversation_id=conversation.id,
                user_id=user.id,
                role=ParticipantRole.ADMIN,
            )
        )
        for member in members:
            self.session.add(
                ConversationParticipant(conversation_id=conversation.id, user_id=member.id)
            )

        await self._add_system_message(
            conversation,
            SystemEvent.GROUP_CREATED,
            {"actor_id": user.id, "name": name},
        )
        await self.session.commit()
        logger.info(
            "group_created",
            extra={"conversation_id": conversation.id, "member_count": len(members) + 1},
        )
        return conversation

    # -- Updating ----------------------------------------------------------

    async def update_conversation(
        self, user: User, conversation_id: str, payload: ConversationUpdate
    ) -> Conversation:
        await self.require_admin(conversation_id, user)
        conversation = await self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("That conversation does not exist.")

        if payload.name is not None:
            if not conversation.is_group:
                raise ValidationError("One-to-one conversations cannot be renamed.")
            conversation.name = payload.name
            await self._add_system_message(
                conversation,
                SystemEvent.GROUP_RENAMED,
                {"actor_id": user.id, "name": payload.name},
            )

        if payload.avatar_url is not None:
            conversation.avatar_url = payload.avatar_url
            await self._add_system_message(
                conversation, SystemEvent.GROUP_AVATAR_CHANGED, {"actor_id": user.id}
            )

        if payload.disappearing_seconds is not None:
            conversation.disappearing_seconds = payload.disappearing_seconds
            await self._add_system_message(
                conversation,
                SystemEvent.DISAPPEARING_TIMER_CHANGED,
                {"actor_id": user.id, "seconds": payload.disappearing_seconds},
            )

        await self.session.commit()
        return conversation

    async def add_participants(
        self, user: User, conversation_id: str, user_ids: list[str]
    ) -> list[User]:
        """Add members to a group. Admin only."""
        await self.require_admin(conversation_id, user)
        conversation = await self.conversations.get(conversation_id)
        if conversation is None or not conversation.is_group:
            raise ValidationError("Only groups can have members added.")

        added: list[User] = []
        for user_id in user_ids:
            candidate = await self.users.get(user_id)
            if candidate is None or not candidate.is_active:
                raise NotFoundError("One or more of those people could not be found.")

            existing = await self.conversations.get_participation(
                conversation_id, user_id, include_left=True
            )
            if existing is not None:
                if existing.left_at is None:
                    # Already a member: skip rather than fail, so adding a group of
                    # people does not abort because one was already present.
                    continue
                # Rejoining reuses the original row, preserving their history.
                existing.left_at = None
                existing.joined_at = utcnow()
            else:
                self.session.add(
                    ConversationParticipant(conversation_id=conversation_id, user_id=user_id)
                )
            added.append(candidate)

        if added:
            await self._add_system_message(
                conversation,
                SystemEvent.MEMBERS_ADDED,
                {"actor_id": user.id, "user_ids": [u.id for u in added]},
            )
        await self.session.commit()
        return added

    async def remove_participant(self, user: User, conversation_id: str, target_id: str) -> None:
        """Remove a member, or leave voluntarily.

        Leaving is always permitted; removing someone else requires admin. Both
        paths set left_at rather than deleting the row, so the person's past
        messages keep a resolvable sender.
        """
        conversation = await self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("That conversation does not exist.")
        if not conversation.is_group:
            raise ValidationError("One-to-one conversations cannot have members removed.")

        leaving = target_id == user.id
        if leaving:
            await self.require_participation(conversation_id, user)
        else:
            await self.require_admin(conversation_id, user)

        target = await self.conversations.get_participation(conversation_id, target_id)
        if target is None:
            raise NotFoundError("That person is not in this group.")

        target.left_at = utcnow()
        await self._add_system_message(
            conversation,
            SystemEvent.MEMBER_LEFT if leaving else SystemEvent.MEMBER_REMOVED,
            {"actor_id": user.id, "user_id": target_id},
        )

        # Never strand a group without an admin: promote the longest-standing
        # remaining member. Otherwise the last admin leaving would make the group
        # permanently unmanageable.
        if target.is_admin:
            remaining = await self.conversations.list_participants([conversation_id])
            active = [
                p
                for p in remaining[conversation_id]
                if p.left_at is None and p.user_id != target_id
            ]
            if active and not any(p.is_admin for p in active):
                active.sort(key=lambda p: p.joined_at)
                active[0].role = ParticipantRole.ADMIN
                await self._add_system_message(
                    conversation,
                    SystemEvent.ROLE_CHANGED,
                    {"user_id": active[0].user_id, "role": ParticipantRole.ADMIN.value},
                )

        await self.session.commit()

    async def mark_read(self, user: User, conversation_id: str, message_id: str) -> None:
        """Advance the caller's read watermark.

        Only ever moves forward. An out-of-order request — common when several
        tabs are open — must not rewind the watermark and resurrect read messages
        as unread.
        """
        participation = await self.require_participation(conversation_id, user)

        target = await self.session.get(Message, message_id)
        if target is None or target.conversation_id != conversation_id:
            raise NotFoundError("That message is not part of this conversation.")

        if participation.last_read_message_id:
            current = await self.session.get(Message, participation.last_read_message_id)
            if current is not None and current.created_at >= target.created_at:
                return

        participation.last_read_message_id = message_id
        await self.session.commit()

    async def set_flags(
        self,
        user: User,
        conversation_id: str,
        *,
        is_muted: bool | None = None,
        is_pinned: bool | None = None,
    ) -> ConversationParticipant:
        """Update the caller's private view of a conversation."""
        participation = await self.require_participation(conversation_id, user)
        if is_muted is not None:
            participation.is_muted = is_muted
        if is_pinned is not None:
            participation.is_pinned = is_pinned
        await self.session.commit()
        return participation

    # -- Internals ---------------------------------------------------------

    async def _add_system_message(
        self, conversation: Conversation, event: SystemEvent, meta: dict[str, Any]
    ) -> Message:
        """Record an event in the transcript.

        System messages share the messages table so the timeline stays a single
        ordered sequence, rather than something the client must merge from two
        sources. last_message_at is advanced in the same transaction, which is
        what keeps the denormalised sort key from drifting.
        """
        message = Message(
            conversation_id=conversation.id,
            sender_id=None,
            type=MessageType.SYSTEM,
            system_event=event,
            system_meta=meta,
        )
        self.session.add(message)
        await self.session.flush()
        conversation.last_message_at = message.created_at
        return message
