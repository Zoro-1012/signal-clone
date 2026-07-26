"""Contact list routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.contact import ContactCreate, ContactRead
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactRead], summary="Your saved contacts")
async def list_contacts(
    current_user: CurrentUser,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=64, description="Filter contacts"),
) -> list[ContactRead]:
    contacts = await ContactService(session).list_contacts(current_user, query=q)
    return [ContactRead.model_validate(contact) for contact in contacts]


@router.post(
    "",
    response_model=ContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Save a contact by phone number or username",
)
async def add_contact(
    payload: ContactCreate, current_user: CurrentUser, session: SessionDep
) -> ContactRead:
    contact = await ContactService(session).add_contact(
        current_user, identifier=payload.identifier, nickname=payload.nickname
    )
    return ContactRead.model_validate(contact)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a contact",
)
async def remove_contact(
    contact_id: str, current_user: CurrentUser, session: SessionDep
) -> Response:
    await ContactService(session).remove_contact(current_user, contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
