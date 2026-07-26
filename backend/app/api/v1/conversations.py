"""Conversation and membership routes."""

from __future__ import annotations

from fastapi import APIRouter, Body, Query, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import MessageResponse
from app.schemas.conversation import (
    ConversationRead,
    ConversationUpdate,
    DirectConversationCreate,
    GroupConversationCreate,
    MarkReadRequest,
    ParticipantsAdd,
)
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get(
    "",
    response_model=list[ConversationRead],
    summary="Your conversations, pinned first then most recent",
)
async def list_conversations(
    current_user: CurrentUser,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=64, description="Filter conversations"),
) -> list[ConversationRead]:
    return await ConversationService(session).list_conversations(current_user, query=q)


@router.post(
    "/direct",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a one-to-one conversation",
)
async def create_direct(
    payload: DirectConversationCreate, current_user: CurrentUser, session: SessionDep
) -> ConversationRead:
    """Idempotent: opening a chat that already exists returns the same one."""
    service = ConversationService(session)
    conversation = await service.create_direct(current_user, payload.user_id)
    return await service.get_conversation(current_user, conversation.id)


@router.post(
    "/group",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a group",
)
async def create_group(
    payload: GroupConversationCreate, current_user: CurrentUser, session: SessionDep
) -> ConversationRead:
    service = ConversationService(session)
    conversation = await service.create_group(
        current_user, name=payload.name, member_ids=payload.member_ids
    )
    return await service.get_conversation(current_user, conversation.id)


@router.get("/{conversation_id}", response_model=ConversationRead, summary="One conversation")
async def get_conversation(
    conversation_id: str, current_user: CurrentUser, session: SessionDep
) -> ConversationRead:
    return await ConversationService(session).get_conversation(current_user, conversation_id)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationRead,
    summary="Rename a group, change its avatar, or set the disappearing timer",
)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> ConversationRead:
    service = ConversationService(session)
    await service.update_conversation(current_user, conversation_id, payload)
    return await service.get_conversation(current_user, conversation_id)


@router.post(
    "/{conversation_id}/participants",
    response_model=ConversationRead,
    summary="Add members to a group (admin only)",
)
async def add_participants(
    conversation_id: str,
    payload: ParticipantsAdd,
    current_user: CurrentUser,
    session: SessionDep,
) -> ConversationRead:
    service = ConversationService(session)
    await service.add_participants(current_user, conversation_id, payload.user_ids)
    return await service.get_conversation(current_user, conversation_id)


@router.delete(
    "/{conversation_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member (admin), or leave the group yourself",
)
async def remove_participant(
    conversation_id: str,
    user_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> Response:
    await ConversationService(session).remove_participant(current_user, conversation_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/read",
    response_model=MessageResponse,
    summary="Advance your read position",
)
async def mark_read(
    conversation_id: str,
    payload: MarkReadRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> MessageResponse:
    await ConversationService(session).mark_read(current_user, conversation_id, payload.message_id)
    return MessageResponse(detail="Read position updated.")


@router.post(
    "/{conversation_id}/flags",
    response_model=ConversationRead,
    summary="Mute or pin a conversation for yourself",
)
async def set_flags(
    conversation_id: str,
    current_user: CurrentUser,
    session: SessionDep,
    is_muted: bool | None = Body(default=None),
    is_pinned: bool | None = Body(default=None),
) -> ConversationRead:
    """Personal view settings — they affect only the caller, not other members."""
    service = ConversationService(session)
    await service.set_flags(current_user, conversation_id, is_muted=is_muted, is_pinned=is_pinned)
    return await service.get_conversation(current_user, conversation_id)
