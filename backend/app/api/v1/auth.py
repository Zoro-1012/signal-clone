"""Authentication and onboarding routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, SessionDep, UserAgent
from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.schemas.auth import (
    ChallengeResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    VerifyRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserPrivate
from app.services.auth_service import AuthService, IssuedSession

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "signal_refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Store the refresh token where JavaScript cannot reach it.

    httpOnly means an XSS payload cannot exfiltrate the long-lived credential.
    In production the frontend and API sit on different origins, so the cookie
    must be SameSite=None, which browsers only accept together with Secure.
    Locally both run over plain HTTP, where Secure would prevent the cookie being
    stored at all — hence the environment-dependent pair.
    """
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")


def _token_response(session: IssuedSession, response: Response) -> TokenResponse:
    _set_refresh_cookie(response, session.refresh_token)
    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in_seconds=session.expires_in_seconds,
        user=UserPrivate.model_validate(session.user),
    )


@router.post(
    "/register",
    response_model=ChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a phone number and receive a verification code",
)
async def register(payload: RegisterRequest, session: SessionDep) -> ChallengeResponse:
    user, code = await AuthService(session).register(
        phone_number=payload.phone_number,
        display_name=payload.display_name,
        username=payload.username,
    )
    return ChallengeResponse(
        phone_number=user.phone_number,
        expires_in_seconds=settings.otp_ttl_seconds,
        # Returned outside production only: verification is mocked by design, and
        # this is what lets a reviewer complete onboarding without an SMS provider.
        dev_code=None if settings.is_production else code,
    )


@router.post(
    "/login",
    response_model=ChallengeResponse,
    summary="Request a verification code for an existing account",
)
async def login(payload: LoginRequest, session: SessionDep) -> ChallengeResponse:
    user, code = await AuthService(session).request_login_code(phone_number=payload.phone_number)
    return ChallengeResponse(
        phone_number=user.phone_number,
        expires_in_seconds=settings.otp_ttl_seconds,
        dev_code=None if settings.is_production else code,
    )


@router.post(
    "/verify",
    response_model=TokenResponse,
    summary="Exchange a verification code for a session",
)
async def verify(
    payload: VerifyRequest,
    session: SessionDep,
    response: Response,
    user_agent: UserAgent,
) -> TokenResponse:
    issued = await AuthService(session).verify(
        phone_number=payload.phone_number,
        code=payload.code,
        user_agent=user_agent,
    )
    return _token_response(issued, response)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate a refresh token for a new session",
)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    user_agent: UserAgent,
    payload: RefreshRequest | None = None,
) -> TokenResponse:
    # Cookie first: a browser should never have to hold the refresh token in
    # JavaScript. The body is the fallback for non-browser clients and tests.
    token = request.cookies.get(REFRESH_COOKIE_NAME) or (payload.refresh_token if payload else None)
    if not token:
        raise AuthenticationError("No session to refresh. Please sign in.")

    issued = await AuthService(session).refresh(refresh_token=token, user_agent=user_agent)
    return _token_response(issued, response)


@router.post("/logout", response_model=MessageResponse, summary="Revoke the current session")
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    payload: RefreshRequest | None = None,
) -> MessageResponse:
    token = request.cookies.get(REFRESH_COOKIE_NAME) or (payload.refresh_token if payload else None)
    await AuthService(session).logout(refresh_token=token)
    _clear_refresh_cookie(response)
    return MessageResponse(detail="Signed out.")


@router.get("/me", response_model=UserPrivate, summary="The currently authenticated account")
async def me(current_user: CurrentUser) -> UserPrivate:
    return UserPrivate.model_validate(current_user)
