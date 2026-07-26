"""Authentication state: one-time codes and refresh sessions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import User


class VerificationCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A pending one-time verification challenge.

    The brief permits mocked phone verification, and the code itself is fixed in
    development. Everything around it is real: a challenge expires, tolerates a
    bounded number of wrong guesses, and can be consumed exactly once. Modelling
    it as a row rather than trusting a constant means the flow exercises the same
    states a real SMS provider would produce, and swapping one in changes only
    how the code is generated and delivered.
    """

    __tablename__ = "verification_codes"

    # Covered by ix_verification_codes_user_created as its leftmost prefix.
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped[User] = relationship("User")

    __table_args__ = (
        # Verification always looks up "the newest live challenge for this user".
        Index("ix_verification_codes_user_created", "user_id", "created_at"),
    )


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A long-lived, revocable session.

    Only the SHA-256 digest is stored, never the token, so a database disclosure
    yields nothing usable. Rotation on every refresh means a stolen token is
    valid for one use at most, and reuse of an already-rotated token is a
    detectable signal that something is wrong.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Context for a "linked devices" style session list, and useful when a user
    # wants to know what is signed in to their account.
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)

    user: Mapped[User] = relationship("User")

    @property
    def is_active(self) -> bool:
        """A token is usable only while unrevoked and unexpired."""
        from app.core.security import utcnow

        return self.revoked_at is None and self.expires_at > utcnow()
