"""The WebSocket endpoint.

One authenticated socket per tab, multiplexing every conversation. Opening a
socket per conversation would multiply connections by conversation count for no
benefit — the frames already carry the conversation they belong to.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.session import get_session_factory
from app.realtime.connection_manager import manager
from app.realtime.events import EventType, build
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.user_repository import UserRepository
from app.services.presence_service import PresenceService

logger = get_logger(__name__)

router = APIRouter()


SessionFactoryDep = Annotated["async_sessionmaker[AsyncSession]", Depends(get_session_factory)]


async def _authenticate(token: str | None, factory: async_sessionmaker[AsyncSession]) -> str | None:
    """Resolve the access token to a user id, or None if it is not usable.

    The token arrives as a query parameter because the browser WebSocket API
    cannot set request headers. That is a real trade-off — query strings are more
    likely to be logged than headers — mitigated by the access token being
    short-lived and by refresh tokens never travelling this way.
    """
    if not token:
        return None
    try:
        user_id = decode_access_token(token)
    except AppError:
        return None

    async with factory() as session:
        user = await UserRepository(session).get(user_id)
        if user is None or not user.is_active:
            return None
    return user_id


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    factory: SessionFactoryDep,
    token: str | None = Query(default=None),
) -> None:
    """Accept a socket, register it, and pump client frames until it closes."""
    user_id = await _authenticate(token, factory)
    if user_id is None:
        # Closed before accepting, so an unauthenticated peer never gets an open
        # socket it could send on.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    await websocket.accept()
    became_online = await manager.connect(user_id, websocket)

    # Everything after registration is guarded. The try must open immediately,
    # not around the receive loop alone: a client that connects and closes at
    # once makes the presence write or the first send raise, and if that happens
    # outside the guard the socket is never deregistered — leaking an entry in
    # the connection registry and leaving the user permanently "online".
    try:
        if became_online:
            async with factory() as session:
                await PresenceService(session).went_online(user_id)

        await websocket.send_json(
            build(EventType.PRESENCE_UPDATE, {"user_id": user_id, "is_online": True})
        )

        while True:
            frame = await websocket.receive_json()
            await _handle(user_id, frame, websocket, factory)
    except WebSocketDisconnect:
        pass
    except Exception:  # a malformed frame must not kill the server
        logger.exception("ws_loop_error", extra={"user_id": user_id})
    finally:
        went_offline = await manager.disconnect(user_id, websocket)
        if went_offline:
            # Only when the *last* socket closes: a user with two tabs who closes
            # one is still online.
            await _record_offline(factory, user_id)


# Strong references to in-flight cleanup tasks. asyncio only holds a weak
# reference to a running task, so without this the garbage collector may destroy
# a shielded task mid-await and the write silently never lands.
CLEANUP_TASKS: set[asyncio.Task[None]] = set()


async def _record_offline(factory: async_sessionmaker[AsyncSession], user_id: str) -> None:
    """Persist the offline transition, surviving the cancellation that caused it.

    Starlette cancels the endpoint task as soon as the socket closes, so any
    bare ``await`` in the ``finally`` block is interrupted before it completes.
    The symptom is subtle and bad: last-seen is never written and the user
    appears permanently online to everyone else.

    Running the write as a shielded task fixes it. Cancellation still propagates
    to *this* coroutine — which is correct, the endpoint is finishing — but the
    inner task is detached and runs to completion.

    A crash still bypasses this entirely, which is why startup reconciles stale
    online flags rather than trusting that this always ran.
    """

    async def _write() -> None:
        async with factory() as session:
            await PresenceService(session).went_offline(user_id)

    task = asyncio.create_task(_write())
    CLEANUP_TASKS.add(task)
    task.add_done_callback(CLEANUP_TASKS.discard)

    with suppress(asyncio.CancelledError):
        await asyncio.shield(task)


async def _handle(
    user_id: str,
    frame: dict[str, Any],
    websocket: WebSocket,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dispatch one client frame.

    Only ephemeral signals are accepted here. Anything that writes to the
    database goes through the REST API, so there is exactly one write path with
    one set of validation and authorisation rules.
    """
    event = frame.get("type")
    payload = frame.get("payload") or {}

    if event == EventType.PING.value:
        await websocket.send_json(build(EventType.PONG))
        return

    if event in {EventType.TYPING_START.value, EventType.TYPING_STOP.value}:
        conversation_id = payload.get("conversation_id")
        if not isinstance(conversation_id, str):
            return

        # Membership is verified rather than trusted: without this, anyone with a
        # valid token could push a typing indicator into any conversation.
        async with factory() as session:
            participation = await ConversationRepository(session).get_participation(
                conversation_id, user_id
            )
            if participation is None:
                return
            participant_ids = await ConversationRepository(session).get_active_participant_ids(
                conversation_id
            )

        starting = event == EventType.TYPING_START.value
        if starting:
            manager.start_typing(conversation_id, user_id)
        else:
            manager.stop_typing(conversation_id, user_id)

        await manager.broadcast(
            participant_ids,
            build(
                EventType.TYPING_START if starting else EventType.TYPING_STOP,
                {"conversation_id": conversation_id, "user_id": user_id},
            ),
            exclude=user_id,  # you do not need to be told that you are typing
        )
        return

    await websocket.send_json(build(EventType.ERROR, {"message": f"Unknown event type: {event!r}"}))


async def disappearing_message_sweeper(
    factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Background loop deleting messages whose timer has elapsed.

    Runs in the application process rather than as a cron job so the demo needs
    no extra infrastructure. A separate worker would be the right answer at scale;
    the trade-off is noted rather than hidden.
    """
    from app.services.message_service import MessageService

    sessions = factory or get_session_factory()

    while True:
        try:
            await asyncio.sleep(settings.disappearing_sweep_seconds)
            async with sessions() as session:
                purged = await MessageService(session).purge_expired()
                if purged:
                    logger.info("sweeper_purged", extra={"count": purged})
        except asyncio.CancelledError:
            # Shutdown, not a failure: re-raise so the task actually stops.
            raise
        except Exception:  # one bad pass must not kill the loop
            logger.exception("sweeper_error")
