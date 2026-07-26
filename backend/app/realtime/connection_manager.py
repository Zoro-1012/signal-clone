"""In-process registry of live WebSocket connections.

Holds the mapping from user to open sockets, and the ephemeral state that only
makes sense while someone is connected: who is online, and who is typing where.

Deliberately in-memory. Presence and typing are worthless a second after they
are produced, so persisting them would mean a database write per keystroke to
store something already stale. The cost is that this is correct for exactly one
process — see ``PROJECT.md`` §3.4 for the Redis pub/sub substitution that makes
it horizontal, which this class's interface is shaped to allow.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger
from app.core.security import utcnow

logger = get_logger(__name__)


class ConnectionManager:
    """Tracks open sockets and fans events out to them."""

    def __init__(self) -> None:
        # One user may hold several sockets at once — several tabs, or a phone and
        # a laptop. Every one of them must receive the same events.
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        # conversation_id -> {user_id: when they last signalled typing}
        self._typing: dict[str, dict[str, datetime]] = defaultdict(dict)
        # Guards the registry against interleaved connect/disconnect coroutines.
        self._lock = asyncio.Lock()

    # -- Registry ----------------------------------------------------------

    async def connect(self, user_id: str, websocket: WebSocket) -> bool:
        """Register an accepted socket. Returns True if the user just came online."""
        async with self._lock:
            was_offline = not self._connections[user_id]
            self._connections[user_id].add(websocket)
        logger.info("ws_connected", extra={"user_id": user_id, "first": was_offline})
        return was_offline

    async def disconnect(self, user_id: str, websocket: WebSocket) -> bool:
        """Deregister a socket. Returns True if the user's last one just closed."""
        async with self._lock:
            self._connections[user_id].discard(websocket)
            now_offline = not self._connections[user_id]
            if now_offline:
                # Drop the empty set so the dict does not grow without bound as
                # users come and go over a long-running process.
                self._connections.pop(user_id, None)
                for typers in self._typing.values():
                    typers.pop(user_id, None)
        logger.info("ws_disconnected", extra={"user_id": user_id, "last": now_offline})
        return now_offline

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def online_user_ids(self) -> set[str]:
        return set(self._connections.keys())

    @property
    def connection_count(self) -> int:
        return sum(len(sockets) for sockets in self._connections.values())

    # -- Delivery ----------------------------------------------------------

    async def send_to_user(self, user_id: str, frame: dict[str, Any]) -> None:
        """Deliver one frame to every socket a user holds."""
        for socket in list(self._connections.get(user_id, ())):
            await self._send(user_id, socket, frame)

    async def broadcast(
        self, user_ids: list[str], frame: dict[str, Any], *, exclude: str | None = None
    ) -> None:
        """Fan one frame out to several users concurrently.

        Gathered rather than awaited in sequence: with a slow or half-open socket
        in the list, sequential sends would make every later recipient wait behind
        it. Offline users are simply absent from the registry — their copy is
        already persisted and will be fetched on next load.
        """
        targets = [uid for uid in set(user_ids) if uid != exclude and uid in self._connections]
        if not targets:
            return
        await asyncio.gather(
            *(self.send_to_user(uid, frame) for uid in targets), return_exceptions=True
        )

    async def _send(self, user_id: str, socket: WebSocket, frame: dict[str, Any]) -> None:
        """Send to one socket, dropping it if the peer has gone.

        A failed send means the connection is already dead; raising here would
        abort the fan-out and deny the event to everyone after this recipient.
        """
        try:
            await socket.send_json(frame)
        except Exception:  # the socket is gone, whatever the specific cause
            logger.debug("ws_send_failed", extra={"user_id": user_id})
            await self.disconnect(user_id, socket)

    # -- Typing ------------------------------------------------------------

    def start_typing(self, conversation_id: str, user_id: str) -> None:
        self._typing[conversation_id][user_id] = utcnow()

    def stop_typing(self, conversation_id: str, user_id: str) -> None:
        self._typing.get(conversation_id, {}).pop(user_id, None)

    def typing_user_ids(self, conversation_id: str, *, timeout_seconds: int) -> list[str]:
        """Who is currently typing, discarding signals that have gone stale.

        A client that closes mid-sentence never sends typing.stop, so an entry
        that is never expired would leave "Alice is typing…" on screen forever.
        Expiry on read costs nothing and needs no background timer.
        """
        typers = self._typing.get(conversation_id)
        if not typers:
            return []
        now = utcnow()
        live = [
            user_id
            for user_id, at in typers.items()
            if (now - at).total_seconds() <= timeout_seconds
        ]
        for user_id in list(typers):
            if user_id not in live:
                typers.pop(user_id, None)
        return live


# Process-wide singleton. The WebSocket endpoint and the message service both
# publish through this one instance.
manager = ConnectionManager()
