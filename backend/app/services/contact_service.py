"""Contact management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contact import Contact
from app.models.user import User
from app.repositories.contact_repository import ContactRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import PHONE_PATTERN, normalise_phone


class ContactService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.contacts = ContactRepository(session)
        self.users = UserRepository(session)

    async def list_contacts(self, owner: User, *, query: str | None = None) -> list[Contact]:
        return await self.contacts.list_for_owner(owner.id, query=query)

    async def add_contact(
        self, owner: User, *, identifier: str, nickname: str | None = None
    ) -> Contact:
        """Save someone to the address book by phone number or username.

        The identifier is normalised only when it looks like a phone number;
        usernames must not be run through E.164 normalisation, which would mangle
        them into something unmatchable.
        """
        cleaned = identifier.strip()
        if cleaned.startswith("+") or cleaned.replace(" ", "").replace("-", "").isdigit():
            cleaned = normalise_phone(cleaned)
        else:
            cleaned = cleaned.lower()

        target = await self.users.get_by_identifier(cleaned)
        if target is None:
            raise NotFoundError(
                "Nobody with that number or username is on Signal yet.",
                code="user_not_found",
            )
        if target.id == owner.id:
            raise ValidationError("You cannot add yourself as a contact.", code="self_contact")

        if await self.contacts.get_edge(owner.id, target.id):
            raise ConflictError("They are already in your contacts.", code="contact_exists")

        contact = Contact(
            owner_id=owner.id,
            contact_user_id=target.id,
            nickname=nickname.strip() if nickname else None,
        )
        self.contacts.add(contact)
        await self.session.commit()
        await self.session.refresh(contact, attribute_names=["contact_user"])
        return contact

    async def remove_contact(self, owner: User, contact_id: str) -> None:
        contact = await self.contacts.get(contact_id)
        # Checking ownership rather than mere existence: responding differently
        # for "not found" and "not yours" would let anyone probe for valid ids.
        if contact is None or contact.owner_id != owner.id:
            raise NotFoundError("That contact does not exist.")
        await self.contacts.delete(contact)
        await self.session.commit()

    async def search_people(self, owner: User, query: str) -> list[User]:
        """Find accounts to start a conversation with, beyond saved contacts."""
        cleaned = query.strip()
        if len(cleaned) < 2:
            return []
        if PHONE_PATTERN.match(cleaned.replace(" ", "")):
            cleaned = normalise_phone(cleaned)
        return await self.users.search(cleaned, exclude_user_id=owner.id)
