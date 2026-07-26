"""Queries over users."""

from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_phone(self, phone_number: str) -> User | None:
        result = await self.session.execute(select(User).where(User.phone_number == phone_number))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == func.lower(username))
        )
        return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> User | None:
        """Resolve a user from either a phone number or a username.

        Callers such as "add a contact" accept whichever the person happens to
        know, so the lookup handles both rather than forcing the UI to guess.
        """
        result = await self.session.execute(
            select(User).where(
                or_(User.phone_number == identifier, User.username == identifier.lower())
            )
        )
        return result.scalar_one_or_none()

    async def search(self, query: str, *, exclude_user_id: str, limit: int = 20) -> list[User]:
        """Case-insensitive search across display name, username and phone number.

        Excludes the caller: offering someone themselves as a search result is
        never useful.
        """
        pattern = f"%{query.lower()}%"
        result = await self.session.execute(
            select(User)
            .where(
                User.id != exclude_user_id,
                User.is_active.is_(True),
                or_(
                    func.lower(User.display_name).like(pattern),
                    func.lower(User.username).like(pattern),
                    User.phone_number.like(pattern),
                ),
            )
            .order_by(User.display_name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_ids(self, user_ids: list[str]) -> list[User]:
        if not user_ids:
            return []
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
        return list(result.scalars().all())
