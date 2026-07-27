"""Queries over messages, receipts and reactions."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, or_, select, update
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from app.core.security import utcnow
from app.models.message import Attachment, Message, MessageReaction, MessageReceipt
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    def _loaded(self) -> tuple[ORMOption, ...]:
        """Eager-load everything the response schema touches.

        ``selectinload`` for the collections rather than ``joinedload``: joining
        three one-to-many relations at once multiplies rows together, so a message
        with 3 reactions and 2 attachments would come back 6 times. selectinload
        issues one extra query per relation and keeps the result set flat.
        """
        return (
            joinedload(Message.sender),
            joinedload(Message.reply_to).joinedload(Message.sender),
            selectinload(Message.attachments),
            selectinload(Message.reactions),
            selectinload(Message.receipts),
        )

    async def get_full(self, message_id: str) -> Message | None:
        """Fetch one message with everything the client needs to render it.

        ``populate_existing`` is required, not optional. If the message is already
        in the session's identity map — which it is whenever we re-read it after a
        write in the same request — SQLAlchemy returns the cached instance and
        leaves its previously loaded collections untouched. Re-reading after
        adding a reaction would then hand back the collection as it looked
        *before* the write, and the response would silently omit it.
        """
        result = await self.session.execute(
            select(Message)
            .options(*self._loaded())
            .where(Message.id == message_id)
            .execution_options(populate_existing=True)
        )
        return result.unique().scalar_one_or_none()

    async def list_page(
        self,
        conversation_id: str,
        *,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[Message]:
        """Return a page of history, newest first.

        Cursor-based, keyed on created_at: a transcript grows while it is being
        read, so an OFFSET would skip or repeat rows as new messages arrive. The
        cursor anchors to a position in the data instead of a count.

        Ordering breaks ties on id because two messages can share a timestamp at
        SQLite's resolution, and an unstable sort would make pagination drop rows.
        """
        statement = (
            select(Message)
            .options(*self._loaded())
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        if before is not None:
            statement = statement.where(Message.created_at < before)

        result = await self.session.execute(statement)
        return list(result.unique().scalars().all())

    async def find_by_client_id(self, sender_id: str, client_message_id: str) -> Message | None:
        """Look up a previous send by its client-generated identifier."""
        result = await self.session.execute(
            select(Message)
            .options(*self._loaded())
            .where(
                Message.sender_id == sender_id,
                Message.client_message_id == client_message_id,
            )
        )
        return result.unique().scalar_one_or_none()

    # -- Receipts ----------------------------------------------------------

    async def ensure_receipts(self, message_id: str, recipient_ids: list[str]) -> None:
        """Create the receipt rows a new message needs, one per recipient."""
        if not recipient_ids:
            return
        self.session.add_all(
            [MessageReceipt(message_id=message_id, user_id=user_id) for user_id in recipient_ids]
        )

    async def mark_delivered(self, user_id: str, conversation_id: str) -> list[str]:
        """Mark everything undelivered in a conversation as delivered to a user.

        Set-based rather than per message: a client returning from offline may
        have hundreds waiting, and issuing one UPDATE per message would turn
        reconnecting into a storm of writes.
        """
        pending = await self.session.execute(
            select(MessageReceipt.message_id)
            .join(Message, Message.id == MessageReceipt.message_id)
            .where(
                MessageReceipt.user_id == user_id,
                MessageReceipt.delivered_at.is_(None),
                Message.conversation_id == conversation_id,
            )
        )
        message_ids = list(pending.scalars().all())
        if not message_ids:
            return []

        await self.session.execute(
            update(MessageReceipt)
            .where(
                MessageReceipt.user_id == user_id,
                MessageReceipt.message_id.in_(message_ids),
                MessageReceipt.delivered_at.is_(None),
            )
            .values(delivered_at=utcnow())
        )
        return message_ids

    async def mark_read(self, user_id: str, conversation_id: str, until: datetime) -> list[str]:
        """Mark every message up to a point as read by a user.

        Delivery is implied by reading: a message cannot be read without having
        arrived, so this backfills delivered_at where a receipt was missed.
        """
        now = utcnow()
        pending = await self.session.execute(
            select(MessageReceipt.message_id)
            .join(Message, Message.id == MessageReceipt.message_id)
            .where(
                MessageReceipt.user_id == user_id,
                MessageReceipt.read_at.is_(None),
                Message.conversation_id == conversation_id,
                Message.created_at <= until,
            )
        )
        message_ids = list(pending.scalars().all())
        if not message_ids:
            return []

        await self.session.execute(
            update(MessageReceipt)
            .where(
                MessageReceipt.user_id == user_id,
                MessageReceipt.message_id.in_(message_ids),
            )
            .values(
                read_at=now,
                delivered_at=func.coalesce(MessageReceipt.delivered_at, now),
            )
        )
        return message_ids

    # -- Reactions ---------------------------------------------------------

    async def get_reaction(
        self, message_id: str, user_id: str, emoji: str
    ) -> MessageReaction | None:
        result = await self.session.execute(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
                MessageReaction.emoji == emoji,
            )
        )
        return result.scalar_one_or_none()

    async def remove_reaction(self, message_id: str, user_id: str, emoji: str) -> int:
        result = await self.session.execute(
            delete(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
                MessageReaction.emoji == emoji,
            )
        )
        # DELETE returns a CursorResult; the base Result protocol has no rowcount.
        return int(cast(CursorResult[Any], result).rowcount or 0)

    # -- Attachments -------------------------------------------------------

    async def get_unattached(self, attachment_ids: list[str]) -> list[Attachment]:
        """Fetch uploads not yet bound to a message.

        Uploading happens before sending, so an attachment briefly exists with no
        message. Only such orphans may be claimed — otherwise one user could
        attach another user's file to their own message by id.
        """
        if not attachment_ids:
            return []
        result = await self.session.execute(
            select(Attachment).where(Attachment.id.in_(attachment_ids))
        )
        return list(result.scalars().all())

    # -- Disappearing messages --------------------------------------------

    async def expired(self, *, limit: int = 500) -> list[Message]:
        """Messages whose disappearing timer has elapsed.

        Attachments are eager-loaded because the sweeper deletes their files
        before deleting the rows, and a lazy load during that pass would emit
        IO from a context that has already left the greenlet.
        """
        result = await self.session.execute(
            select(Message)
            .options(selectinload(Message.attachments))
            .where(
                Message.expires_at.is_not(None),
                Message.expires_at <= utcnow(),
                Message.deleted_at.is_(None),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def start_expiry_timers(self, message_ids: list[str], seconds: int) -> None:
        """Begin the countdown for messages that have just been delivered.

        The timer starts on delivery rather than on creation: a message that has
        not reached the recipient yet should not be counting down, or a slow
        connection would silently consume the whole window.
        """
        if not message_ids or seconds <= 0:
            return

        # Computed in Python rather than as a SQL interval expression: SQLite has
        # no INTERVAL type, and its date arithmetic is string-based, so building
        # this in SQL would be both dialect-specific and easy to get subtly wrong.
        expires_at = utcnow() + timedelta(seconds=seconds)

        await self.session.execute(
            update(Message)
            .where(
                Message.id.in_(message_ids),
                # Only start a timer that is not already running, so a second
                # recipient's delivery cannot extend the window.
                Message.expires_at.is_(None),
            )
            .values(expires_at=expires_at)
        )

    async def search(self, user_id: str, query: str, *, limit: int = 30) -> list[Message]:
        """Search message text the caller can see.

        Content is sealed, so SQL cannot match against it. Candidates are narrowed
        to the caller's conversations here and matched after decryption in the
        service — the honest cost of storing ciphertext, and the reason the limit
        is bounded.
        """
        from app.models.conversation import ConversationParticipant

        result = await self.session.execute(
            select(Message)
            .options(joinedload(Message.sender))
            .join(
                ConversationParticipant,
                ConversationParticipant.conversation_id == Message.conversation_id,
            )
            .where(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
                Message.deleted_at.is_(None),
                or_(Message.type == "text", Message.type == "media"),
            )
            .order_by(Message.created_at.desc())
            .limit(limit * 20)
        )
        return list(result.unique().scalars().all())
