"""Sending, reading and reacting to messages.

The send path is deliberately ordered: persist, then broadcast. The database is
the source of truth and the socket only accelerates delivery of something already
committed. Doing it the other way round would let a recipient see a message that
a failed transaction then rolled back.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import Envelope, cipher
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import utcnow
from app.models.conversation import Conversation
from app.models.enums import MessageStatus, MessageType
from app.models.message import Attachment, Message, MessageReaction
from app.models.user import User
from app.realtime.connection_manager import ConnectionManager, manager
from app.realtime.events import EventType, build
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.cursor import encode_cursor
from app.schemas.message import (
    AttachmentRead,
    MessageCreate,
    MessageRead,
    QuotedMessage,
    ReactionSummary,
)
from app.schemas.user import UserPublic
from app.services.conversation_service import ConversationService
from app.services.storage import storage

logger = get_logger(__name__)

QUOTE_PREVIEW_LENGTH = 140


class MessageService:
    def __init__(self, session: AsyncSession, *, events: ConnectionManager | None = None) -> None:
        self.session = session
        self.messages = MessageRepository(session)
        self.conversations = ConversationRepository(session)
        self.conversation_service = ConversationService(session)
        # Injected so tests can substitute a recorder, and so the in-memory
        # manager can later be swapped for a Redis-backed one without touching
        # this class.
        self.events = events or manager

    # -- Reading -----------------------------------------------------------

    async def list_messages(
        self,
        user: User,
        conversation_id: str,
        *,
        before: datetime | None = None,
        limit: int = 50,
    ) -> tuple[list[MessageRead], str | None]:
        """Return a page of history plus the cursor for the next one."""
        await self.conversation_service.require_participation(conversation_id, user)

        # Fetch one extra row to learn whether another page exists, without a
        # second COUNT query over the whole conversation.
        rows = await self.messages.list_page(conversation_id, before=before, limit=limit + 1)
        has_more = len(rows) > limit
        rows = rows[:limit]

        participant_count = len(
            await self.conversations.get_active_participant_ids(conversation_id)
        )
        items = [
            self._to_read(row, viewer=user, participant_count=participant_count) for row in rows
        ]
        next_cursor = encode_cursor(rows[-1].created_at) if (rows and has_more) else None
        return items, next_cursor

    async def get_message(self, user: User, message_id: str) -> MessageRead:
        message = await self.messages.get_full(message_id)
        if message is None:
            raise NotFoundError("That message does not exist.")
        await self.conversation_service.require_participation(message.conversation_id, user)
        count = len(await self.conversations.get_active_participant_ids(message.conversation_id))
        return self._to_read(message, viewer=user, participant_count=count)

    # -- Sending -----------------------------------------------------------

    async def send(self, user: User, conversation_id: str, payload: MessageCreate) -> MessageRead:
        """Persist a message, then push it to everyone connected."""
        await self.conversation_service.require_participation(conversation_id, user)
        conversation = await self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("That conversation does not exist.")

        if not payload.body and not payload.attachment_ids:
            raise ValidationError("A message needs text or an attachment.")

        # Retry safety. A client that timed out and resent carries the same
        # client_message_id; returning the original is what makes the send
        # idempotent rather than duplicating the message.
        if payload.client_message_id:
            existing = await self.messages.find_by_client_id(user.id, payload.client_message_id)
            if existing is not None:
                count = len(await self.conversations.get_active_participant_ids(conversation_id))
                return self._to_read(existing, viewer=user, participant_count=count)

        if payload.reply_to_message_id:
            quoted = await self.messages.get(payload.reply_to_message_id)
            if quoted is None or quoted.conversation_id != conversation_id:
                # Quoting across conversations would leak content from a thread
                # the recipients may not be in.
                raise ValidationError("You can only reply to a message in this conversation.")

        attachments = await self._claim_attachments(payload.attachment_ids)

        envelope = cipher.seal(payload.body) if payload.body else None
        message = Message(
            conversation_id=conversation_id,
            sender_id=user.id,
            type=MessageType.MEDIA if attachments else MessageType.TEXT,
            ciphertext=envelope.ciphertext if envelope else None,
            encryption_key_id=envelope.key_id if envelope else None,
            encryption_algorithm=envelope.algorithm if envelope else None,
            reply_to_message_id=payload.reply_to_message_id,
            client_message_id=payload.client_message_id,
        )
        self.session.add(message)
        await self.session.flush()

        for attachment in attachments:
            attachment.message_id = message.id

        participant_ids = await self.conversations.get_active_participant_ids(conversation_id)
        recipients = [uid for uid in participant_ids if uid != user.id]
        await self.messages.ensure_receipts(message.id, recipients)

        # Same transaction as the message, so the conversation-list sort key can
        # never disagree with the transcript.
        conversation.last_message_at = message.created_at
        await self.session.commit()

        stored = await self.messages.get_full(message.id)
        assert stored is not None  # just committed
        view = self._to_read(stored, viewer=user, participant_count=len(participant_ids))

        await self._broadcast_new(stored, conversation, participant_ids, sender_id=user.id)
        logger.info(
            "message_sent",
            extra={"conversation_id": conversation_id, "recipients": len(recipients)},
        )
        return view

    async def _broadcast_new(
        self,
        message: Message,
        conversation: Conversation,
        participant_ids: list[str],
        *,
        sender_id: str,
    ) -> None:
        """Push a committed message to each participant's own view of it.

        Rendered per recipient rather than once: ``reacted_by_me`` and the derived
        status differ by viewer, so a single shared payload would be wrong for
        everyone but the sender.
        """
        for user_id in participant_ids:
            frame = build(
                EventType.MESSAGE_NEW,
                {
                    "conversation_id": conversation.id,
                    "message": self._to_read(
                        message,
                        viewer_id=user_id,
                        participant_count=len(participant_ids),
                    ).model_dump(mode="json"),
                },
            )
            await self.events.send_to_user(user_id, frame)

        # The sender's own devices need the conversation row refreshed too, so an
        # open list reorders without a refetch.
        await self.events.broadcast(
            participant_ids,
            build(
                EventType.CONVERSATION_UPDATED,
                {
                    "conversation_id": conversation.id,
                    "last_message_at": message.created_at.isoformat(),
                },
            ),
            exclude=sender_id,
        )

    async def _claim_attachments(self, attachment_ids: list[str]) -> list[Attachment]:
        """Bind previously uploaded files to this message.

        Only unbound uploads may be claimed. Without that check, passing another
        user's attachment id would attach their file to your message.
        """
        if not attachment_ids:
            return []
        found = await self.messages.get_unattached(attachment_ids)
        if len(found) != len(set(attachment_ids)):
            raise ValidationError("One or more attachments could not be found.")
        for attachment in found:
            if attachment.message_id is not None:
                raise ValidationError("That attachment has already been sent.")
        return list(found)

    # -- Editing and deleting ---------------------------------------------

    async def edit(self, user: User, message_id: str, body: str) -> MessageRead:
        message = await self.messages.get_full(message_id)
        if message is None:
            raise NotFoundError("That message does not exist.")
        if message.sender_id != user.id:
            raise PermissionDeniedError("You can only edit your own messages.")
        if message.deleted_at is not None:
            raise ValidationError("That message was deleted.")
        if message.type == MessageType.SYSTEM:
            raise ValidationError("System messages cannot be edited.")

        envelope = cipher.seal(body)
        message.ciphertext = envelope.ciphertext
        message.encryption_key_id = envelope.key_id
        message.encryption_algorithm = envelope.algorithm
        message.edited_at = utcnow()
        await self.session.commit()

        participant_ids = await self.conversations.get_active_participant_ids(
            message.conversation_id
        )
        for user_id in participant_ids:
            await self.events.send_to_user(
                user_id,
                build(
                    EventType.MESSAGE_UPDATED,
                    {
                        "conversation_id": message.conversation_id,
                        "message": self._to_read(
                            message, viewer_id=user_id, participant_count=len(participant_ids)
                        ).model_dump(mode="json"),
                    },
                ),
            )
        return self._to_read(message, viewer=user, participant_count=len(participant_ids))

    async def delete(self, user: User, message_id: str) -> None:
        """Soft-delete a message, leaving a tombstone.

        The row survives so the client can render "This message was deleted" in
        place, and so receipts and replies that reference it stay intact.
        """
        message = await self.messages.get(message_id)
        if message is None:
            raise NotFoundError("That message does not exist.")
        if message.sender_id != user.id:
            raise PermissionDeniedError("You can only delete your own messages.")

        message.deleted_at = utcnow()
        message.ciphertext = None
        message.encryption_key_id = None
        message.encryption_algorithm = None
        await self.session.commit()

        participant_ids = await self.conversations.get_active_participant_ids(
            message.conversation_id
        )
        await self.events.broadcast(
            participant_ids,
            build(
                EventType.MESSAGE_DELETED,
                {"conversation_id": message.conversation_id, "message_id": message.id},
            ),
        )

    # -- Reactions ---------------------------------------------------------

    async def react(self, user: User, message_id: str, emoji: str) -> MessageRead:
        """Toggle an emoji reaction.

        Tapping the same emoji twice removes it, which is what the UI affordance
        implies and avoids needing a separate 'remove' interaction.
        """
        message = await self.messages.get_full(message_id)
        if message is None:
            raise NotFoundError("That message does not exist.")
        await self.conversation_service.require_participation(message.conversation_id, user)

        existing = await self.messages.get_reaction(message_id, user.id, emoji)
        if existing is not None:
            await self.messages.remove_reaction(message_id, user.id, emoji)
            event = EventType.REACTION_REMOVED
        else:
            self.session.add(MessageReaction(message_id=message_id, user_id=user.id, emoji=emoji))
            event = EventType.REACTION_ADDED
        await self.session.commit()

        refreshed = await self.messages.get_full(message_id)
        assert refreshed is not None
        participant_ids = await self.conversations.get_active_participant_ids(
            message.conversation_id
        )
        await self.events.broadcast(
            participant_ids,
            build(
                event,
                {
                    "conversation_id": message.conversation_id,
                    "message_id": message_id,
                    "user_id": user.id,
                    "emoji": emoji,
                },
            ),
        )
        return self._to_read(refreshed, viewer=user, participant_count=len(participant_ids))

    # -- Receipts ----------------------------------------------------------

    async def mark_delivered(self, user: User, conversation_id: str) -> list[str]:
        """Acknowledge arrival of everything outstanding in a conversation.

        Also starts disappearing timers: the countdown should begin when a message
        can actually be read, not when it was sent, or a slow connection would
        silently consume the window.
        """
        await self.conversation_service.require_participation(conversation_id, user)
        message_ids = await self.messages.mark_delivered(user.id, conversation_id)

        conversation = await self.conversations.get(conversation_id)
        if conversation and conversation.disappearing_seconds > 0 and message_ids:
            await self.messages.start_expiry_timers(message_ids, conversation.disappearing_seconds)

        if message_ids:
            await self.session.commit()
            await self._broadcast_status(
                conversation_id, message_ids, MessageStatus.DELIVERED, user
            )
        return message_ids

    async def mark_read(self, user: User, conversation_id: str, until_message_id: str) -> list[str]:
        """Record that the caller has read up to a given message."""
        await self.conversation_service.require_participation(conversation_id, user)

        target = await self.messages.get(until_message_id)
        if target is None or target.conversation_id != conversation_id:
            raise NotFoundError("That message is not part of this conversation.")

        message_ids = await self.messages.mark_read(user.id, conversation_id, target.created_at)
        await self.conversation_service.mark_read(user, conversation_id, until_message_id)

        if message_ids:
            await self._broadcast_status(conversation_id, message_ids, MessageStatus.READ, user)
        return message_ids

    async def _broadcast_status(
        self,
        conversation_id: str,
        message_ids: list[str],
        status: MessageStatus,
        actor: User,
    ) -> None:
        """Tell participants that receipts moved.

        Sent as one frame listing every affected message rather than one frame per
        message: returning from offline can move hundreds at once, and a frame
        each would flood the socket.
        """
        participant_ids = await self.conversations.get_active_participant_ids(conversation_id)
        await self.events.broadcast(
            participant_ids,
            build(
                EventType.MESSAGE_STATUS,
                {
                    "conversation_id": conversation_id,
                    "message_ids": message_ids,
                    "status": status.value,
                    "user_id": actor.id,
                },
            ),
            exclude=actor.id,
        )

    # -- Disappearing messages --------------------------------------------

    async def purge_expired(self) -> int:
        """Delete messages whose timer has elapsed. Returns how many."""
        expired = await self.messages.expired()
        if not expired:
            return 0

        by_conversation: dict[str, list[str]] = defaultdict(list)
        for message in expired:
            message.deleted_at = utcnow()
            message.ciphertext = None
            message.encryption_key_id = None
            message.encryption_algorithm = None
            by_conversation[message.conversation_id].append(message.id)
        await self.session.commit()

        for conversation_id, message_ids in by_conversation.items():
            participant_ids = await self.conversations.get_active_participant_ids(conversation_id)
            for message_id in message_ids:
                await self.events.broadcast(
                    participant_ids,
                    build(
                        EventType.MESSAGE_DELETED,
                        {"conversation_id": conversation_id, "message_id": message_id},
                    ),
                )
        logger.info("disappearing_messages_purged", extra={"count": len(expired)})
        return len(expired)

    # -- Projection --------------------------------------------------------

    def _to_read(
        self,
        message: Message,
        *,
        viewer: User | None = None,
        viewer_id: str | None = None,
        participant_count: int = 2,
    ) -> MessageRead:
        """Render a stored message for one particular viewer."""
        who = viewer.id if viewer else viewer_id

        body: str | None = None
        if message.deleted_at is None and message.ciphertext:
            body = cipher.open(
                Envelope(
                    ciphertext=message.ciphertext,
                    key_id=message.encryption_key_id or "",
                    algorithm=message.encryption_algorithm or "",
                )
            )

        delivered = sum(1 for r in message.receipts if r.delivered_at is not None)
        read = sum(1 for r in message.receipts if r.read_at is not None)
        recipient_count = max(participant_count - 1, 0)

        return MessageRead(
            id=message.id,
            conversation_id=message.conversation_id,
            sender=UserPublic.model_validate(message.sender) if message.sender else None,
            type=message.type,
            body=body,
            created_at=message.created_at,
            edited_at=message.edited_at,
            deleted_at=message.deleted_at,
            expires_at=message.expires_at,
            reply_to=self._quote(message.reply_to),
            attachments=[
                AttachmentRead(
                    id=a.id,
                    file_name=a.file_name,
                    content_type=a.content_type,
                    size_bytes=a.size_bytes,
                    width=a.width,
                    height=a.height,
                    url=storage.url_for(a.storage_key),
                    thumbnail_url=storage.url_for(a.thumbnail_key) if a.thumbnail_key else None,
                )
                for a in message.attachments
            ],
            reactions=self._aggregate_reactions(message, who),
            system_event=message.system_event.value if message.system_event else None,
            system_meta=message.system_meta,
            client_message_id=message.client_message_id,
            status=self._derive_status(delivered, read, recipient_count),
            delivered_count=delivered,
            read_count=read,
            recipient_count=recipient_count,
        )

    @staticmethod
    def _derive_status(delivered: int, read: int, recipient_count: int) -> MessageStatus:
        """Collapse per-recipient receipts into the single glyph the UI shows.

        Signal's convention: the double blue check appears only once *everyone*
        has read it, so the weakest recipient's state governs. In a group of
        seven, six having read is still 'delivered'.
        """
        if recipient_count == 0:
            return MessageStatus.SENT
        if read >= recipient_count:
            return MessageStatus.READ
        if delivered >= recipient_count:
            return MessageStatus.DELIVERED
        return MessageStatus.SENT

    @staticmethod
    def _aggregate_reactions(message: Message, viewer_id: str | None) -> list[ReactionSummary]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for reaction in message.reactions:
            grouped[reaction.emoji].append(reaction.user_id)
        return [
            ReactionSummary(
                emoji=emoji,
                count=len(user_ids),
                user_ids=user_ids,
                reacted_by_me=viewer_id in user_ids if viewer_id else False,
            )
            # Most-reacted first, then alphabetically so ordering is stable
            # between renders rather than following dict insertion order.
            for emoji, user_ids in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ]

    @staticmethod
    def _quote(message: Message | None) -> QuotedMessage | None:
        if message is None:
            return None
        preview = ""
        if message.deleted_at is None and message.ciphertext:
            preview = cipher.open(
                Envelope(
                    ciphertext=message.ciphertext,
                    key_id=message.encryption_key_id or "",
                    algorithm=message.encryption_algorithm or "",
                )
            )[:QUOTE_PREVIEW_LENGTH]
        return QuotedMessage(
            id=message.id,
            sender_id=message.sender_id,
            sender_display_name=message.sender.display_name if message.sender else None,
            preview=preview,
            type=message.type,
            is_deleted=message.deleted_at is not None,
        )
