"""Repository base class.

Repositories are the only layer permitted to build SQL. Services describe intent
("find the user with this phone number"); repositories decide how that becomes a
query. Keeping the split means a query can be optimised without touching a
business rule, and business rules can be read without wading through joins.

Repositories never commit. The service owns the transaction boundary, so several
repository calls can succeed or fail as one unit.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Shared plumbing for concrete repositories."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: str) -> ModelT | None:
        """Fetch by primary key, or None."""
        return await self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        """Stage a new row. Flushed by the caller when its identity is needed."""
        self.session.add(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)

    async def flush(self) -> None:
        """Push pending changes so server-generated values become readable."""
        await self.session.flush()
