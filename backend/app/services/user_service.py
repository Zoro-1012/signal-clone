"""Profile management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def update_profile(self, user: User, payload: UserUpdate) -> User:
        """Apply a partial profile update.

        Only fields explicitly present in the request are touched. Using
        ``exclude_unset`` rather than checking for None is what allows a field to
        be deliberately cleared — sending ``about: null`` blanks it, whereas
        omitting the field leaves it alone. Those are different intentions and the
        API should be able to express both.
        """
        changes = payload.model_dump(exclude_unset=True)

        if "username" in changes and changes["username"] is not None:
            existing = await self.users.get_by_username(changes["username"])
            if existing is not None and existing.id != user.id:
                raise ConflictError("That username is already taken.", code="username_taken")

        for field, value in changes.items():
            setattr(user, field, value)

        await self.session.commit()
        await self.session.refresh(user)
        return user
