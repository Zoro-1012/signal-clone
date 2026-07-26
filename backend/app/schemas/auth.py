"""Authentication request and response schemas."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.common import APIModel
from app.schemas.user import USERNAME_PATTERN, UserPrivate, normalise_phone


class RegisterRequest(APIModel):
    """Start registration for a new phone number."""

    phone_number: str = Field(..., examples=["+919876543210"])
    display_name: str = Field(..., min_length=1, max_length=64)
    username: str | None = Field(default=None, min_length=3, max_length=32)

    @field_validator("phone_number")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return normalise_phone(value)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.strip().lower()
        if not USERNAME_PATTERN.match(lowered):
            raise ValueError(
                "Usernames may contain only lowercase letters, numbers, underscores "
                "and dots, and must be 3-32 characters long."
            )
        return lowered

    @field_validator("display_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class LoginRequest(APIModel):
    """Request a fresh verification code for an existing account."""

    phone_number: str = Field(..., examples=["+919876543210"])

    @field_validator("phone_number")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return normalise_phone(value)


class VerifyRequest(APIModel):
    """Exchange a verification code for a session."""

    phone_number: str
    code: str = Field(..., min_length=4, max_length=10)

    @field_validator("phone_number")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return normalise_phone(value)

    @field_validator("code")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class ChallengeResponse(APIModel):
    """Acknowledges that a verification code has been issued.

    ``dev_code`` is populated only outside production. Verification is mocked by
    design (see the brief), and surfacing the code here is what lets a reviewer
    complete the flow without an SMS provider. The production branch omits it, so
    the mock cannot silently become a live vulnerability.
    """

    phone_number: str
    expires_in_seconds: int
    dev_code: str | None = None
    detail: str = "Verification code sent."


class TokenResponse(APIModel):
    """A newly issued session.

    The refresh token is also set as an httpOnly cookie. It is returned in the
    body as well so that non-browser clients and the test suite can drive the
    flow without cookie handling — a browser should prefer the cookie, which
    JavaScript cannot read and therefore cannot leak through XSS.
    """

    access_token: str
    refresh_token: str
    # Not a credential: this is the OAuth 2.0 scheme name the client puts in the
    # Authorization header. Bandit's S105 matches on the variable name alone.
    token_type: str = "bearer"  # noqa: S105
    expires_in_seconds: int
    user: UserPrivate


class RefreshRequest(APIModel):
    """Optional body for refresh, when no cookie is available."""

    refresh_token: str | None = None
