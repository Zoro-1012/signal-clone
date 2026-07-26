"""Queries over the contact list."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.models.contact import Contact
from app.models.user import User
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    async def list_for_owner(self, owner_id: str, *, query: str | None = None) -> list[Contact]:
        """Return an owner's contacts, optionally filtered.

        The related user is eager-loaded: every contact is rendered with the
        person's name, avatar and presence, so lazy-loading would issue one extra
        query per row — the classic N+1 — and under async SQLAlchemy would raise
        rather than merely be slow.
        """
        statement = (
            select(Contact)
            .options(joinedload(Contact.contact_user))
            .join(User, User.id == Contact.contact_user_id)
            .where(Contact.owner_id == owner_id)
        )
        if query:
            pattern = f"%{query.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(User.display_name).like(pattern),
                    func.lower(User.username).like(pattern),
                    User.phone_number.like(pattern),
                    func.lower(Contact.nickname).like(pattern),
                )
            )
        statement = statement.order_by(func.lower(User.display_name))
        result = await self.session.execute(statement)
        return list(result.scalars().unique().all())

    async def get_edge(self, owner_id: str, contact_user_id: str) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(
                Contact.owner_id == owner_id,
                Contact.contact_user_id == contact_user_id,
            )
        )
        return result.scalar_one_or_none()
