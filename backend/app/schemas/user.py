"""User and profile schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import APIModel

# E.164: a leading +, a non-zero country digit, then up to 14 more digits.
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
USERNAME_PATTERN = re.compile(r"^[a-z0-9_.]{3,32}$")


def normalise_phone(value: str) -> str:
    """Reduce a phone number to canonical E.164.

    Users type numbers with spaces, dashes and brackets. Without normalisation the
    same person could register twice and never find each other, because the unique
    constraint compares raw strings.
    """
    cleaned = re.sub(r"[\s\-().]", "", value.strip())
    if not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    if not PHONE_PATTERN.match(cleaned):
        raise ValueError(
            "Enter a valid phone number in international format, for example +919876543210."
        )
    return cleaned


class UserPublic(APIModel):
    """Another person as they appear to you.

    Deliberately excludes phone_number: it is the login identifier, and exposing
    every participant's number to everyone in a group would leak personal contact
    details that Signal treats as private.
    """

    id: str
    username: str | None
    display_name: str
    about: str | None
    avatar_url: str | None
    avatar_color: str
    is_online: bool
    last_seen_at: datetime | None


class UserPrivate(UserPublic):
    """Your own account, which does include the identifying phone number."""

    phone_number: str
    created_at: datetime


class UserUpdate(APIModel):
    """Editable profile fields. Every field optional — this is a partial update."""

    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    about: str | None = Field(default=None, max_length=140)
    username: str | None = Field(default=None, min_length=3, max_length=32)

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

    @field_validator("display_name", "about")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value
