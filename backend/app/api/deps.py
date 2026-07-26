"""Shared FastAPI dependencies.

Anything more than one router needs — the database session, the authenticated
user — is resolved here, so authentication is declared once and applied
consistently instead of being re-implemented per route.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User
from app.repositories.user_repository import UserRepository

# auto_error=False so a missing header raises our own AuthenticationError, keeping
# the response envelope identical to every other failure the API can produce.
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer access token")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Resolve the authenticated user, or reject the request.

    The token is verified cryptographically and the user is then loaded, because a
    signature alone does not prove the account still exists or is still active — a
    deactivated user must stop being able to act, immediately, without waiting for
    their access token to expire.
    """
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Sign in to continue.")

    user_id = decode_access_token(credentials.credentials)
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("This account is no longer active.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_user_agent(request: Request) -> str | None:
    """Client description, recorded against a session for the devices list."""
    return request.headers.get("user-agent")


UserAgent = Annotated[str | None, Depends(get_user_agent)]
