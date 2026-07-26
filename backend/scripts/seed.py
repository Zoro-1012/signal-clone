"""Seed the database with a realistic, immediately usable dataset.

The brief asks for seeded data so the app is usable on first load. Running this
twice must be safe, so it is idempotent: it detects an existing seed and stops
unless ``--reset`` is passed.

Timestamps are backdated and spread across several days so the conversation list
sorts meaningfully and date dividers in the transcript have something to divide.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.core.avatars import pick_avatar_color
from app.core.encryption import cipher
from app.db.base import Base
from app.db.session import SessionFactory, engine
from app.models import (
    Contact,
    Conversation,
    ConversationParticipant,
    Message,
    MessageReaction,
    MessageReceipt,
    RefreshToken,
    User,
    VerificationCode,
)
from app.models.enums import (
    ConversationType,
    MessageType,
    ParticipantRole,
    SystemEvent,
)

# Deterministic, so re-seeding produces the same demo every time and a reviewer
# following the README sees exactly what it describes.
random.seed(20260726)

NOW = datetime.now(timezone.utc)

PEOPLE = [
    ("+919876543210", "nipurn", "Nipurn Goyal", "Building things."),
    ("+919812345678", "ananya", "Ananya Sharma", "Designer · Bengaluru"),
    ("+919823456789", "rohan", "Rohan Verma", "Coffee, code, cricket"),
    ("+919834567890", "meera", "Meera Iyer", "Photographer"),
    ("+919845678901", "kabir", "Kabir Nair", None),
    ("+919856789012", "ishaan", "Ishaan Rao", "Away from keyboard"),
]

DIRECT_SCRIPTS: dict[str, list[tuple[str, int, str]]] = {
    "ananya": [
        ("ananya", 52, "Morning! Did the revised mockups land in your inbox?"),
        ("nipurn", 51, "Just opened them. The spacing on the settings screen is much better."),
        ("ananya", 51, "That was the main fix. I also tightened the type scale."),
        ("nipurn", 50, "Noticed. It reads far cleaner at small sizes now."),
        ("ananya", 26, "Are we still reviewing at 4?"),
        ("nipurn", 25, "Yes, 4 works. I'll bring the latest build."),
        ("ananya", 3, "Perfect, see you then \U0001f44d"),
    ],
    "rohan": [
        ("rohan", 30, "Match on Sunday? Ground is booked from 7."),
        ("nipurn", 29, "I'm in. Do we have eleven?"),
        ("rohan", 29, "Nine confirmed. Kabir says he'll bring a friend."),
        ("nipurn", 28, "Then we're basically there. I'll get the kit."),
        ("rohan", 5, "Weather looks clear all weekend"),
    ],
    "meera": [
        ("meera", 74, "Sent over the photos from last weekend."),
        ("nipurn", 73, "These are lovely. The one by the water especially."),
        ("meera", 72, "That's my favourite too. Golden hour did all the work."),
        ("nipurn", 20, "Do you mind if I use it as a wallpaper?"),
        ("meera", 19, "Go ahead!"),
    ],
}

GROUP_SCRIPT = [
    ("nipurn", 96, "Right — Goa planning starts now."),
    ("ananya", 95, "Dates? I can do the 14th to the 18th."),
    ("rohan", 95, "Same here. 14th works."),
    ("meera", 94, "Works for me too. Shall I look at places to stay?"),
    ("nipurn", 94, "Please. Somewhere north, near the quieter beaches."),
    ("meera", 70, "Found three options. Sending the links tonight."),
    ("rohan", 46, "Anyone driving down, or are we all flying?"),
    ("ananya", 45, "Flying. Tickets are still reasonable if we book this week."),
    ("nipurn", 22, "Booked mine. 14th, morning flight."),
    ("meera", 21, "Same flight as you, I think."),
    ("rohan", 4, "Booked. See you both at the airport \U0001f334"),
]

STUDY_SCRIPT = [
    ("nipurn", 40, "Starting the system design notes tonight if anyone wants to join."),
    ("kabir", 39, "I'm in. Which chapter?"),
    ("nipurn", 39, "Consistency models, then replication."),
    ("ishaan", 38, "Save me a seat, I'll catch up tomorrow."),
    ("kabir", 8, "Notes were genuinely good. Thanks for sharing."),
]


def _at(hours_ago: float) -> datetime:
    return NOW - timedelta(hours=hours_ago)


async def _ensure_schema() -> None:
    """Create tables if absent, so a first run works on an empty database."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _already_seeded() -> bool:
    async with SessionFactory() as session:
        found = await session.execute(select(User).where(User.phone_number == PEOPLE[0][0]))
        return found.scalar_one_or_none() is not None


async def _wipe() -> None:
    """Delete seeded data. Order respects foreign keys."""
    async with SessionFactory() as session:
        for model in (
            MessageReaction,
            MessageReceipt,
            Message,
            ConversationParticipant,
            Conversation,
            Contact,
            RefreshToken,
            VerificationCode,
            User,
        ):
            await session.execute(delete(model))
        await session.commit()
    print("Existing data cleared.")


def _sealed(body: str) -> dict[str, str]:
    envelope = cipher.seal(body)
    return {
        "ciphertext": envelope.ciphertext,
        "encryption_key_id": envelope.key_id,
        "encryption_algorithm": envelope.algorithm,
    }


async def seed() -> None:
    async with SessionFactory() as session:
        users: dict[str, User] = {}
        for phone, username, display_name, about in PEOPLE:
            user = User(
                phone_number=phone,
                username=username,
                display_name=display_name,
                about=about,
                avatar_color=pick_avatar_color(phone),
                # Two people are left online so presence indicators are visible
                # immediately, without needing a second browser open.
                is_online=username in {"ananya", "rohan"},
                last_seen_at=_at(random.uniform(0.2, 30)),
            )
            session.add(user)
            users[username] = user
        await session.flush()

        owner = users["nipurn"]

        # Everyone is in the owner's address book, so search and the new-chat
        # picker have something to show on first load.
        for username, user in users.items():
            if username != "nipurn":
                session.add(Contact(owner_id=owner.id, contact_user_id=user.id))

        async def add_messages(
            conversation: Conversation,
            script: list[tuple[str, int, str]] | list[tuple[str, float, str]],
            members: list[User],
        ) -> Message | None:
            last: Message | None = None
            previous: Message | None = None
            for index, (author, hours_ago, body) in enumerate(script):
                created = _at(float(hours_ago))
                message = Message(
                    conversation_id=conversation.id,
                    sender_id=users[author].id,
                    type=MessageType.TEXT,
                    created_at=created,
                    updated_at=created,
                    # One reply per script, to exercise quoting in the UI.
                    reply_to_message_id=(
                        previous.id if index == 3 and previous is not None else None
                    ),
                    **_sealed(body),
                )
                session.add(message)
                await session.flush()

                # Receipts for everyone except the sender. Recent messages from
                # others are left unread so the list shows unread badges.
                recent_from_other = hours_ago < 6 and author != "nipurn"
                for member in members:
                    if member.id == message.sender_id:
                        continue
                    is_owner = member.id == owner.id
                    session.add(
                        MessageReceipt(
                            message_id=message.id,
                            user_id=member.id,
                            delivered_at=created + timedelta(seconds=2),
                            read_at=(
                                None
                                if (is_owner and recent_from_other)
                                else created + timedelta(minutes=1)
                            ),
                        )
                    )
                previous = message
                last = message

            if last is not None:
                conversation.last_message_at = last.created_at
            return last

        # --- Direct conversations ----------------------------------------
        for username, script in DIRECT_SCRIPTS.items():
            other = users[username]
            conversation = Conversation(
                type=ConversationType.DIRECT,
                created_by=owner.id,
                direct_key=Conversation.build_direct_key(owner.id, other.id),
                created_at=_at(script[0][1] + 1),
                updated_at=_at(script[0][1] + 1),
            )
            session.add(conversation)
            await session.flush()
            session.add_all(
                [
                    ConversationParticipant(conversation_id=conversation.id, user_id=owner.id),
                    ConversationParticipant(conversation_id=conversation.id, user_id=other.id),
                ]
            )
            await add_messages(conversation, script, [owner, other])

        # --- Group: Goa Trip ---------------------------------------------
        goa_members = [owner, users["ananya"], users["rohan"], users["meera"]]
        goa = Conversation(
            type=ConversationType.GROUP,
            name="Goa Trip 2026",
            created_by=owner.id,
            created_at=_at(97),
            updated_at=_at(97),
            # A live disappearing timer, so the feature is visible without setup.
            disappearing_seconds=0,
        )
        session.add(goa)
        await session.flush()
        for member in goa_members:
            session.add(
                ConversationParticipant(
                    conversation_id=goa.id,
                    user_id=member.id,
                    role=ParticipantRole.ADMIN if member is owner else ParticipantRole.MEMBER,
                )
            )
        session.add(
            Message(
                conversation_id=goa.id,
                sender_id=None,
                type=MessageType.SYSTEM,
                system_event=SystemEvent.GROUP_CREATED,
                system_meta={"actor_id": owner.id, "name": "Goa Trip 2026"},
                created_at=_at(97),
                updated_at=_at(97),
            )
        )
        last_goa = await add_messages(goa, GROUP_SCRIPT, goa_members)

        # A couple of reactions on the most recent group message.
        if last_goa is not None:
            for username, emoji in (("ananya", "\U0001f44d"), ("meera", "\U0001f334")):
                session.add(
                    MessageReaction(message_id=last_goa.id, user_id=users[username].id, emoji=emoji)
                )

        # --- Group: Study ------------------------------------------------
        study_members = [owner, users["kabir"], users["ishaan"]]
        study = Conversation(
            type=ConversationType.GROUP,
            name="System Design Study",
            created_by=owner.id,
            created_at=_at(41),
            updated_at=_at(41),
        )
        session.add(study)
        await session.flush()
        for member in study_members:
            session.add(
                ConversationParticipant(
                    conversation_id=study.id,
                    user_id=member.id,
                    role=ParticipantRole.ADMIN if member is owner else ParticipantRole.MEMBER,
                )
            )
        session.add(
            Message(
                conversation_id=study.id,
                sender_id=None,
                type=MessageType.SYSTEM,
                system_event=SystemEvent.GROUP_CREATED,
                system_meta={"actor_id": owner.id, "name": "System Design Study"},
                created_at=_at(41),
                updated_at=_at(41),
            )
        )
        await add_messages(study, STUDY_SCRIPT, study_members)

        await session.commit()

    await engine.dispose()


def _report() -> None:
    print("\nSeed complete. Sign in with any of these numbers:\n")
    for phone, username, display_name, _ in PEOPLE:
        print(f"  {display_name:<16} {phone:<16} @{username}")
    print("\n  Verification code for every account: 123456")
    print("  Suggested demo account: +919876543210 (Nipurn Goyal)\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Signal clone database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing data before seeding.",
    )
    args = parser.parse_args()

    await _ensure_schema()

    if await _already_seeded():
        if not args.reset:
            print(
                "Database already contains seed data. "
                "Re-run with --reset to clear it and seed again."
            )
            await engine.dispose()
            return
        await _wipe()

    await seed()
    _report()


if __name__ == "__main__":
    asyncio.run(main())
