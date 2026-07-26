"""Shared schema building blocks."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIModel(BaseModel):
    """Base for every response schema.

    ``from_attributes`` lets a schema be built straight from an ORM object, which
    is what keeps routers free of hand-written field mapping while still ensuring
    no ORM instance is ever serialised directly to the wire.
    """

    model_config = ConfigDict(from_attributes=True)


class CursorPage(APIModel, Generic[T]):
    """A page of results plus the cursor needed to fetch the next one.

    Cursor rather than offset pagination: a transcript grows while it is being
    read, and offsets shift under insertions, so page 2 of an offset query can
    skip or repeat rows. A cursor anchored to a row is stable regardless of what
    arrives in the meantime.
    """

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class MessageResponse(APIModel):
    """Trivial acknowledgement for endpoints with nothing meaningful to return."""

    detail: str
