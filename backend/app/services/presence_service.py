"""Online/last-seen tracking."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.realtime.connection_manager import ConnectionManager, manager
from app.realtime.events import EventType, build
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.user_repository import UserRepository


class PresenceService:
    """Keeps the stored presence columns in step with live connections.

    ``is_online`` mirrors whether a socket is open, and ``last_seen_at`` is the
    durable value shown once it is not. Persisting last-seen matters because it
    has to survive a restart; persisting online-ness does not, which is why it is
    reconciled at startup rather than trusted.
    """

    def __init__(self, session: AsyncSession, *, events: ConnectionManager | None = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.conversations = ConversationRepository(session)
        self.events = events or manager

    async def went_online(self, user_id: str) -> None:
        user = await self.users.get(user_id)
        if user is None:
            return
        user.is_online = True
        user.last_seen_at = utcnow()
        await self.session.commit()
        await self._announce(user_id, is_online=True, last_seen_at=user.last_seen_at)

    async def went_offline(self, user_id: str) -> None:
        user = await self.users.get(user_id)
        if user is None:
            return
        user.is_online = False
        user.last_seen_at = utcnow()
        await self.session.commit()
        await self._announce(user_id, is_online=False, last_seen_at=user.last_seen_at)

    async def _announce(self, user_id: str, *, is_online: bool, last_seen_at: object) -> None:
        """Tell only the people who share a conversation with this user."""
        peers = await self.conversations.get_peer_user_ids(user_id)
        if not peers:
            return
        await self.events.broadcast(
            peers,
            build(
                EventType.PRESENCE_UPDATE,
                {
                    "user_id": user_id,
                    "is_online": is_online,
                    "last_seen_at": (
                        last_seen_at.isoformat() if hasattr(last_seen_at, "isoformat") else None
                    ),
                },
            ),
        )

    async def reset_all(self) -> int:
        """Clear stale online flags at startup.

        A process that is killed never runs its disconnect handlers, so every
        user who was connected stays marked online forever. Reconciling on boot
        is what keeps presence honest across a crash or a redeploy.
        """
        from sqlalchemy import update

        from app.models.user import User

        result = await self.session.execute(
            update(User).where(User.is_online.is_(True)).values(is_online=False)
        )
        await self.session.commit()
        from typing import Any, cast

        from sqlalchemy import CursorResult

        return int(cast("CursorResult[Any]", result).rowcount or 0)
