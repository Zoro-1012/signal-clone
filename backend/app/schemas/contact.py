"""Contact schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.common import APIModel
from app.schemas.user import UserPublic


class ContactCreate(APIModel):
    """Add someone by whichever identifier the person happens to know."""

    identifier: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="A phone number in international format, or a username.",
        examples=["+919876543210", "nipurn"],
    )
    nickname: str | None = Field(default=None, max_length=64)


class ContactRead(APIModel):
    """A saved contact, with the underlying account attached."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    nickname: str | None
    created_at: datetime
    # Exposed as `user` because that is what it means to a client, while the ORM
    # relationship is `contact_user` to stay unambiguous next to `owner`. The
    # alias keeps the wire contract readable without renaming the model.
    user: UserPublic = Field(validation_alias="contact_user")

    @property
    def display_label(self) -> str:
        """What to show: the owner's nickname wins over the person's own name."""
        return self.nickname or self.user.display_name
