"""Message routes, including attachments."""

from __future__ import annotations

import io

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, SessionDep
from app.core.exceptions import NotFoundError, ValidationError
from app.models.message import Attachment
from app.schemas.common import CursorPage, MessageResponse
from app.schemas.cursor import decode_cursor
from app.schemas.message import (
    AttachmentRead,
    MessageCreate,
    MessageRead,
    MessageUpdate,
    ReactionCreate,
)
from app.services.message_service import MessageService
from app.services.storage import storage

router = APIRouter(tags=["messages"])


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=CursorPage[MessageRead],
    summary="Conversation history, newest first",
)
async def list_messages(
    conversation_id: str,
    current_user: CurrentUser,
    session: SessionDep,
    cursor: str | None = Query(
        default=None, description="Opaque cursor from a previous page's next_cursor"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> CursorPage[MessageRead]:
    """Cursor-paginated: an offset would skip rows as new messages arrive."""
    items, next_cursor = await MessageService(session).list_messages(
        current_user, conversation_id, before=decode_cursor(cursor) if cursor else None, limit=limit
    )
    return CursorPage(items=items, next_cursor=next_cursor, has_more=next_cursor is not None)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message",
)
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> MessageRead:
    """Sends go over HTTP, not the socket.

    The socket is a delivery channel, not the write path: this way every send has
    a real status code and natural retry semantics, and the app degrades to
    polling rather than breaking when the connection drops.
    """
    return await MessageService(session).send(current_user, conversation_id, payload)


@router.post(
    "/conversations/{conversation_id}/delivered",
    response_model=MessageResponse,
    summary="Acknowledge delivery of everything outstanding",
)
async def mark_delivered(
    conversation_id: str, current_user: CurrentUser, session: SessionDep
) -> MessageResponse:
    ids = await MessageService(session).mark_delivered(current_user, conversation_id)
    return MessageResponse(detail=f"{len(ids)} message(s) marked delivered.")


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/read",
    response_model=MessageResponse,
    summary="Mark read up to a message",
)
async def mark_read(
    conversation_id: str, message_id: str, current_user: CurrentUser, session: SessionDep
) -> MessageResponse:
    ids = await MessageService(session).mark_read(current_user, conversation_id, message_id)
    return MessageResponse(detail=f"{len(ids)} message(s) marked read.")


@router.patch("/messages/{message_id}", response_model=MessageRead, summary="Edit a message")
async def edit_message(
    message_id: str, payload: MessageUpdate, current_user: CurrentUser, session: SessionDep
) -> MessageRead:
    return await MessageService(session).edit(current_user, message_id, payload.body)


@router.delete(
    "/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a message, leaving a tombstone",
)
async def delete_message(
    message_id: str, current_user: CurrentUser, session: SessionDep
) -> Response:
    await MessageService(session).delete(current_user, message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/messages/{message_id}/reactions",
    response_model=MessageRead,
    summary="Toggle an emoji reaction",
)
async def toggle_reaction(
    message_id: str, payload: ReactionCreate, current_user: CurrentUser, session: SessionDep
) -> MessageRead:
    """Idempotent toggle: the same emoji twice removes it."""
    return await MessageService(session).react(current_user, message_id, payload.emoji)


@router.post(
    "/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file, to be attached to a message",
)
async def upload_attachment(
    current_user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
) -> AttachmentRead:
    """Upload first, send second.

    Decoupling the two means a large file uploads while the person is still
    typing, and a failed send does not lose the upload.
    """
    data = await file.read()
    if not data:
        raise ValidationError("The uploaded file is empty.")

    key = await storage.save(
        data,
        filename=file.filename or "attachment",
        content_type=file.content_type or "application/octet-stream",
    )

    width = height = None
    if (file.content_type or "").startswith("image/"):
        # Intrinsic dimensions let the client reserve space before the image
        # loads, so the transcript does not jump as media arrives.
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
        except Exception:  # a corrupt or unsupported image is not a fatal upload
            width = height = None

    attachment = Attachment(
        message_id=None,
        file_name=file.filename or "attachment",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        storage_key=key,
        width=width,
        height=height,
    )
    session.add(attachment)
    await session.commit()

    return AttachmentRead(
        id=attachment.id,
        file_name=attachment.file_name,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        width=attachment.width,
        height=attachment.height,
        url=storage.url_for(attachment.storage_key),
    )


@router.get(
    "/attachments/{storage_key:path}",
    summary="Download an attachment",
    response_class=FileResponse,
)
async def download_attachment(storage_key: str) -> FileResponse:
    """Serve a stored file.

    The path is resolved through the storage backend, which refuses any key that
    escapes the upload root — the key arrives from a URL, so traversal is checked
    rather than assumed.
    """
    path = storage.path_for(storage_key)
    if path is None or not path.exists() or not path.is_file():
        raise NotFoundError("That attachment does not exist.")
    return FileResponse(path)
