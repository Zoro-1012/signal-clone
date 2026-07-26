"""The contact list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import User


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A directed edge from one user to another.

    Deliberately one-way, like a phone's address book: saving someone's number
    does not put you in theirs, and it must not require their consent. A mutual
    relationship is simply two rows.

    ``nickname`` lets the owner override how the contact is displayed without
    touching that person's own profile.
    """

    __tablename__ = "contacts"

    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)

    owner: Mapped[User] = relationship("User", foreign_keys=[owner_id], back_populates="contacts")
    contact_user: Mapped[User] = relationship("User", foreign_keys=[contact_user_id])

    __table_args__ = (
        # The same person cannot appear twice in one address book. Enforced by the
        # database, not just by service code, so a race between two concurrent
        # "add contact" requests cannot produce a duplicate.
        UniqueConstraint("owner_id", "contact_user_id", name="uq_contact_owner_target"),
    )
