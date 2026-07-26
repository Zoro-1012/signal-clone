"""Queries over conversations and membership.

The conversation list is the most frequently loaded screen in the application,
so it is built from a fixed number of set-based queries rather than by walking
relationships. Every method here returns data for *all* requested conversations
at once; the service layer then assembles them. This keeps the cost independent
of how many conversations a user has.
"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import joinedload

from app.models.conversation import Conversation, ConversationParticipant
from app.models.message import Message
from app.models.user import User
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    # -- Membership --------------------------------------------------------

    async def get_participation(
        self, conversation_id: str, user_id: str, *, include_left: bool = False
    ) -> ConversationParticipant | None:
        """Return a user's membership row, which is also the authorisation check.

        Every conversation-scoped operation begins here: no membership row means
        no access, so permission is decided by data rather than by a rule that
        each endpoint has to remember to apply.
        """
        statement = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        )
        if not include_left:
            statement = statement.where(ConversationParticipant.left_at.is_(None))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_participants(
        self, conversation_ids: list[str], *, include_left: bool = True
    ) -> dict[str, list[ConversationParticipant]]:
        """Members of many conversations, grouped by conversation.

        One query for the whole list rather than one per conversation.
        """
        if not conversation_ids:
            return {}
        statement = (
            select(ConversationParticipant)
            .options(joinedload(ConversationParticipant.user))
            .where(ConversationParticipant.conversation_id.in_(conversation_ids))
        )
        if not include_left:
            statement = statement.where(ConversationParticipant.left_at.is_(None))
        result = await self.session.execute(statement)

        grouped: dict[str, list[ConversationParticipant]] = {cid: [] for cid in conversation_ids}
        for participant in result.scalars().unique().all():
            grouped[participant.conversation_id].append(participant)
        return grouped

    async def get_active_participant_ids(self, conversation_id: str) -> list[str]:
        """User ids currently in a conversation — the WebSocket fan-out list."""
        result = await self.session.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        return list(result.scalars().all())

    # -- Lookup ------------------------------------------------------------

    async def get_direct(self, user_id_a: str, user_id_b: str) -> Conversation | None:
        """Find the existing one-to-one conversation between two people, if any."""
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.direct_key == Conversation.build_direct_key(user_id_a, user_id_b)
            )
        )
        return result.scalar_one_or_none()

    def _for_user(self, user_id: str) -> Select[tuple[Conversation]]:
        return (
            select(Conversation)
            .join(
                ConversationParticipant,
                ConversationParticipant.conversation_id == Conversation.id,
            )
            .where(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )

    async def list_for_user(self, user_id: str, *, query: str | None = None) -> list[Conversation]:
        """A user's conversations, ordered the way the list renders them.

        Pinned first, then most recent activity. Ordering by the denormalised
        last_message_at is an index scan; deriving it from the messages table
        would mean a correlated subquery per conversation on every load.

        NULLs sort last explicitly: a conversation with no messages yet belongs at
        the bottom, and SQLite would otherwise place NULL first.
        """
        statement = self._for_user(user_id)
        if query:
            pattern = f"%{query.lower()}%"
            # Match a group by its name, or a direct conversation by the other
            # person's name. The correlated EXISTS keeps this to one query.
            other_person = (
                select(ConversationParticipant.id)
                .join(User, User.id == ConversationParticipant.user_id)
                .where(
                    ConversationParticipant.conversation_id == Conversation.id,
                    ConversationParticipant.user_id != user_id,
                    or_(
                        func.lower(User.display_name).like(pattern),
                        func.lower(User.username).like(pattern),
                    ),
                )
                .exists()
            )
            statement = statement.where(
                or_(func.lower(Conversation.name).like(pattern), other_person)
            )

        statement = statement.order_by(
            ConversationParticipant.is_pinned.desc(),
            Conversation.last_message_at.is_(None),
            Conversation.last_message_at.desc(),
            Conversation.created_at.desc(),
        )
        result = await self.session.execute(statement)
        return list(result.scalars().unique().all())

    # -- List decoration ---------------------------------------------------

    async def latest_messages(self, conversation_ids: list[str]) -> dict[str, Message]:
        """The newest surviving message in each conversation.

        A window function ranks messages per conversation and keeps only the
        first, so this is one query for the entire list. The obvious alternative
        — fetch each conversation's messages and take the last — would read the
        whole transcript to display one line.
        """
        if not conversation_ids:
            return {}

        ranked = (
            select(
                Message.id.label("message_id"),
                func.row_number()
                .over(
                    partition_by=Message.conversation_id,
                    order_by=(Message.created_at.desc(), Message.id.desc()),
                )
                .label("rank"),
            )
            .where(
                Message.conversation_id.in_(conversation_ids),
                Message.deleted_at.is_(None),
            )
            .subquery()
        )

        result = await self.session.execute(
            select(Message)
            .options(joinedload(Message.sender))
            .join(ranked, ranked.c.message_id == Message.id)
            .where(ranked.c.rank == 1)
        )
        return {message.conversation_id: message for message in result.scalars().unique().all()}

    async def unread_counts(self, user_id: str, conversation_ids: list[str]) -> dict[str, int]:
        """Unread message counts, derived from each read watermark.

        Counts messages newer than the watermark that the user did not send.
        Deriving rather than storing a counter is what makes this correct under
        concurrency: marking the same message read twice cannot double-decrement,
        because nothing is being decremented.
        """
        if not conversation_ids:
            return {}

        watermark = select(Message.id, Message.created_at).subquery()

        result = await self.session.execute(
            select(Message.conversation_id, func.count(Message.id))
            .join(
                ConversationParticipant,
                (ConversationParticipant.conversation_id == Message.conversation_id)
                & (ConversationParticipant.user_id == user_id),
            )
            .outerjoin(
                watermark,
                watermark.c.id == ConversationParticipant.last_read_message_id,
            )
            .where(
                Message.conversation_id.in_(conversation_ids),
                Message.deleted_at.is_(None),
                # A user's own messages are read by definition.
                or_(Message.sender_id.is_(None), Message.sender_id != user_id),
                # No watermark yet means the whole conversation is unread.
                or_(
                    watermark.c.created_at.is_(None),
                    Message.created_at > watermark.c.created_at,
                ),
            )
            .group_by(Message.conversation_id)
        )
        return {row[0]: row[1] for row in result.all()}
