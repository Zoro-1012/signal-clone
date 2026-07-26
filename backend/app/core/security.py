"""Token issuing, verification and hashing primitives.

Signal-style onboarding is password-less: identity is proven by consuming a
one-time code, after which the server issues a short-lived access token and a
long-lived rotating refresh token.

Why two tokens: the access token is a stateless JWT that every request can
verify without touching the database, but that also means it cannot be revoked,
so it expires quickly. The refresh token *is* database-backed and therefore
revocable — logging out deletes it, which is what makes logout meaningful.
Refresh tokens are stored only as SHA-256 digests, so a database disclosure
does not hand an attacker usable sessions.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError

TokenType = Literal["access", "refresh"]


def utcnow() -> datetime:
    """Timezone-aware current UTC time.

    Used everywhere instead of ``datetime.utcnow()``, which returns a naive
    value and silently compares wrong against aware timestamps.
    """
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Access tokens (stateless JWT)
# ---------------------------------------------------------------------------


def create_access_token(user_id: str, *, expires_delta: timedelta | None = None) -> str:
    """Mint a signed access token identifying ``user_id``."""
    expire = utcnow() + (expires_delta or timedelta(minutes=settings.access_token_ttl_minutes))
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "access",
        "iat": int(utcnow().timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Verify an access token and return its subject.

    Raises ``AuthenticationError`` — never a JWT library error — so callers deal
    with one exception type and no library detail leaks into the API layer.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Your session has expired.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid authentication token.", code="token_invalid") from exc

    if payload.get("type") != "access":
        # Reject a refresh token presented as a bearer credential: the two have
        # different lifetimes and revocation semantics and must not be interchangeable.
        raise AuthenticationError("Invalid authentication token.", code="token_invalid")

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthenticationError("Invalid authentication token.", code="token_invalid")
    return subject


# ---------------------------------------------------------------------------
# Refresh tokens (opaque, database-backed, revocable)
# ---------------------------------------------------------------------------


def generate_refresh_token() -> str:
    """Return a high-entropy opaque refresh token.

    Opaque rather than a JWT: it carries no claims, so it cannot be read or
    relied upon by the client, and its only meaning is the database row it maps to.
    """
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Digest a token for storage. Never store the token itself."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(candidate: str, stored_hash: str) -> bool:
    """Constant-time comparison, so timing cannot be used to guess a token."""
    return hmac.compare_digest(hash_token(candidate), stored_hash)


def refresh_token_expiry() -> datetime:
    return utcnow() + timedelta(days=settings.refresh_token_ttl_days)


# ---------------------------------------------------------------------------
# One-time verification codes
# ---------------------------------------------------------------------------


def generate_verification_code() -> str:
    """Issue an OTP.

    Returns the fixed code while `mock_verification` is on, which the brief
    permits and which is what makes the demo usable without an SMS provider.

    The switch is deliberately independent of `environment`. Tying it to
    "not production" meant the deployed app generated a random code and had
    nowhere to deliver it, locking every user out - the mock has to be turned
    off in the same change that wires up a real provider, not implicitly by
    setting an environment name.
    """
    if settings.mock_verification:
        return settings.mock_otp_code
    return f"{secrets.randbelow(1_000_000):06d}"


def codes_match(candidate: str, stored: str) -> bool:
    return hmac.compare_digest(candidate.strip(), stored)


def verification_code_expiry() -> datetime:
    return utcnow() + timedelta(seconds=settings.otp_ttl_seconds)
