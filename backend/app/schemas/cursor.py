"""Opaque pagination cursors.

A cursor is a position in a result set, not a value the client should read or
construct. Encoding it keeps that boundary honest, and — concretely — avoids a
trap: an ISO-8601 UTC timestamp ends in ``+00:00``, and ``+`` decodes to a space
in a query string, so a raw timestamp cursor silently fails the moment it is put
in a URL.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime

from app.core.exceptions import ValidationError


def encode_cursor(value: datetime) -> str:
    """Encode a position as a URL-safe token."""
    raw = value.isoformat().encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: str) -> datetime:
    """Decode a token back to a position, rejecting anything malformed."""
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        return datetime.fromisoformat(raw.decode("utf-8"))
    except (ValueError, binascii.Error) as exc:
        raise ValidationError("That pagination cursor is not valid.", code="bad_cursor") from exc
