"""Registration, verification and session lifecycle.

Owns the transaction boundary for every auth operation: a registration either
creates the user *and* its challenge, or neither.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.avatars import pick_avatar_color
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)
from app.core.logging import get_logger
from app.core.security import (
    codes_match,
    create_access_token,
    generate_refresh_token,
    generate_verification_code,
    hash_token,
    refresh_token_expiry,
    utcnow,
    verification_code_expiry,
)
from app.models.auth import RefreshToken, VerificationCode
from app.models.user import User
from app.repositories.auth_repository import (
    RefreshTokenRepository,
    VerificationCodeRepository,
)
from app.repositories.user_repository import UserRepository

logger = get_logger(__name__)


@dataclass(frozen=True)
class IssuedSession:
    """The pair of tokens produced by a successful authentication."""

    access_token: str
    refresh_token: str
    expires_in_seconds: int
    user: User


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.codes = VerificationCodeRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    # -- Registration and code issuance -----------------------------------

    async def register(
        self, *, phone_number: str, display_name: str, username: str | None
    ) -> tuple[User, str]:
        """Create an account and issue its first verification challenge.

        Both uniqueness checks are made explicitly so the caller gets a precise,
        actionable message. The database constraints remain the real guarantee —
        these checks lose to a concurrent request, and the constraint is what
        stops a duplicate from ever being written.
        """
        if await self.users.get_by_phone(phone_number):
            raise ConflictError(
                "That phone number is already registered. Try signing in instead.",
                code="phone_taken",
            )
        if username and await self.users.get_by_username(username):
            raise ConflictError("That username is already taken.", code="username_taken")

        user = User(
            phone_number=phone_number,
            display_name=display_name,
            username=username,
            avatar_color=pick_avatar_color(phone_number),
        )
        self.users.add(user)
        await self.session.flush()

        code = await self._issue_code(user)
        await self.session.commit()

        logger.info("user_registered", extra={"user_id": user.id})
        return user, code

    async def request_login_code(self, *, phone_number: str) -> tuple[User, str]:
        """Issue a fresh challenge for an existing account."""
        user = await self.users.get_by_phone(phone_number)
        if user is None:
            raise NotFoundError(
                "No account exists for that phone number. Create one to get started.",
                code="account_not_found",
            )
        code = await self._issue_code(user)
        await self.session.commit()
        return user, code

    async def _issue_code(self, user: User) -> str:
        """Invalidate any outstanding challenge and create exactly one live code."""
        await self.codes.invalidate_all_for_user(user.id)
        code = generate_verification_code()
        self.codes.add(
            VerificationCode(
                user_id=user.id,
                code=code,
                expires_at=verification_code_expiry(),
            )
        )
        await self.session.flush()
        return code

    # -- Verification ------------------------------------------------------

    async def verify(
        self, *, phone_number: str, code: str, user_agent: str | None = None
    ) -> IssuedSession:
        """Consume a verification code and open a session.

        Wrong guesses are counted on the challenge row. Once the limit is reached
        the challenge is burned rather than merely rejected, so an attacker cannot
        keep guessing against the same code — they must request a new one, which
        is observable by the account owner.
        """
        user = await self.users.get_by_phone(phone_number)
        if user is None:
            raise NotFoundError("No account exists for that phone number.")

        challenge = await self.codes.get_latest_active(user.id)
        if challenge is None:
            raise AuthenticationError(
                "That code has expired. Request a new one.", code="code_expired"
            )

        if challenge.attempts >= settings.otp_max_attempts:
            challenge.consumed_at = utcnow()
            await self.session.commit()
            raise RateLimitError(
                "Too many incorrect attempts. Request a new code.", code="too_many_attempts"
            )

        if not codes_match(code, challenge.code):
            challenge.attempts += 1
            await self.session.commit()
            remaining = max(settings.otp_max_attempts - challenge.attempts, 0)
            raise AuthenticationError(
                f"That code is not correct. {remaining} attempt(s) remaining.",
                code="code_invalid",
            )

        challenge.consumed_at = utcnow()
        session = await self._open_session(user, user_agent=user_agent)
        await self.session.commit()

        logger.info("user_verified", extra={"user_id": user.id})
        return session

    # -- Sessions ----------------------------------------------------------

    async def _open_session(self, user: User, *, user_agent: str | None) -> IssuedSession:
        """Mint an access/refresh pair and persist the refresh token's digest."""
        raw_refresh = generate_refresh_token()
        self.refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw_refresh),
                expires_at=refresh_token_expiry(),
                user_agent=(user_agent or "")[:256] or None,
            )
        )
        await self.session.flush()
        return IssuedSession(
            access_token=create_access_token(user.id),
            refresh_token=raw_refresh,
            expires_in_seconds=settings.access_token_ttl_minutes * 60,
            user=user,
        )

    async def refresh(self, *, refresh_token: str, user_agent: str | None = None) -> IssuedSession:
        """Rotate a refresh token.

        The presented token is revoked and replaced, so a captured token is usable
        at most once. Presenting an already-revoked token is treated as a signal
        that it may have been stolen: every session for that account is revoked,
        because the alternative is letting an attacker keep a foothold.
        """
        stored = await self.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if stored is None:
            raise AuthenticationError("Invalid session. Please sign in again.")

        if stored.revoked_at is not None:
            await self.refresh_tokens.revoke_all_for_user(stored.user_id)
            await self.session.commit()
            logger.warning("refresh_token_reuse_detected", extra={"user_id": stored.user_id})
            raise AuthenticationError(
                "This session is no longer valid. Please sign in again.",
                code="token_reused",
            )

        if stored.expires_at <= utcnow():
            raise AuthenticationError("Your session has expired. Please sign in again.")

        user = await self.users.get(stored.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("This account is no longer active.")

        stored.revoked_at = utcnow()
        session = await self._open_session(user, user_agent=user_agent)
        await self.session.commit()
        return session

    async def logout(self, *, refresh_token: str | None) -> None:
        """Revoke a single session.

        Absent or unknown tokens succeed silently: logout must be idempotent, and
        reporting whether a token existed would leak information to an attacker.
        """
        if not refresh_token:
            return
        stored = await self.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if stored and stored.revoked_at is None:
            stored.revoked_at = utcnow()
            await self.session.commit()
