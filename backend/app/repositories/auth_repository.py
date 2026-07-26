"""Queries over verification codes and refresh sessions."""

from __future__ import annotations

from sqlalchemy import select, update

from app.core.security import utcnow
from app.models.auth import RefreshToken, VerificationCode
from app.repositories.base import BaseRepository


class VerificationCodeRepository(BaseRepository[VerificationCode]):
    model = VerificationCode

    async def get_latest_active(self, user_id: str) -> VerificationCode | None:
        """Return the newest challenge that is still usable, if any.

        "Newest" matters: requesting a second code must not leave the first one
        valid, or an attacker who observed an earlier code retains a way in.
        """
        result = await self.session.execute(
            select(VerificationCode)
            .where(
                VerificationCode.user_id == user_id,
                VerificationCode.consumed_at.is_(None),
                VerificationCode.expires_at > utcnow(),
            )
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def invalidate_all_for_user(self, user_id: str) -> None:
        """Consume every outstanding challenge for a user.

        Called before issuing a new one, so exactly one code is ever live.
        """
        await self.session.execute(
            update(VerificationCode)
            .where(
                VerificationCode.user_id == user_id,
                VerificationCode.consumed_at.is_(None),
            )
            .values(consumed_at=utcnow())
        )


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Sign out every session for a user."""
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )

    async def purge_expired(self) -> int:
        """Delete sessions that can no longer be used.

        Housekeeping: expired rows can never authenticate anything, so retaining
        them only grows the table and the index.
        """
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.expires_at < utcnow())
        )
        rows = list(result.scalars().all())
        for row in rows:
            await self.session.delete(row)
        return len(rows)
