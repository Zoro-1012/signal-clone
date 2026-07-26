"""Profile and people-search routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.user import UserPrivate, UserPublic, UserUpdate
from app.services.contact_service import ContactService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPrivate, summary="Your own profile")
async def read_me(current_user: CurrentUser) -> UserPrivate:
    return UserPrivate.model_validate(current_user)


@router.patch("/me", response_model=UserPrivate, summary="Update your profile")
async def update_me(
    payload: UserUpdate, current_user: CurrentUser, session: SessionDep
) -> UserPrivate:
    updated = await UserService(session).update_profile(current_user, payload)
    return UserPrivate.model_validate(updated)


@router.get(
    "/search",
    response_model=list[UserPublic],
    summary="Find people by name, username or phone number",
)
async def search_users(
    current_user: CurrentUser,
    session: SessionDep,
    q: str = Query(..., min_length=2, max_length=64, description="Search term"),
) -> list[UserPublic]:
    """Search all accounts, not only saved contacts.

    Starting a conversation should not require adding someone first — Signal lets
    you message a number you have not saved.
    """
    people = await ContactService(session).search_people(current_user, q)
    return [UserPublic.model_validate(person) for person in people]
