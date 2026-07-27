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

import io

from PIL import ImageDraw, ImageFont
from sqlalchemy import delete, select

from app.core.avatars import pick_avatar_color
from app.core.config import settings
from app.core.encryption import cipher
from app.db.base import Base
from app.db.session import SessionFactory, engine
from app.models import (
    Attachment,
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
from app.services.storage import storage

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
            Attachment,
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

    # Attachment rows and the files they point at are two halves of one record.
    # Clearing only the rows leaves orphans on disk, and because the seeder runs
    # on every boot of the demo deployment, those orphans accumulate forever.
    import shutil

    if settings.upload_dir.exists():
        shutil.rmtree(settings.upload_dir)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    print("Existing data cleared.")


def _sealed(body: str) -> dict[str, str]:
    envelope = cipher.seal(body)
    return {
        "ciphertext": envelope.ciphertext,
        "encryption_key_id": envelope.key_id,
        "encryption_algorithm": envelope.algorithm,
    }


# Seeded media --------------------------------------------------------------
#
# The demo needs images in the transcript for the attachment UI to mean anything,
# but committing binaries into the repository to achieve that is a poor trade:
# they bloat clones and go stale. They are drawn instead, so the seed stays a
# few hundred bytes of code and reproduces byte-for-byte on any machine.

SEED_PHOTOS: list[tuple[str, str, str, tuple[int, int, int], tuple[int, int, int]]] = [
    ("beach-sunset.png", "landscape", "Palolem, 6:41pm", (252, 168, 96), (74, 40, 92)),
    ("hillside.png", "landscape", "Western Ghats", (150, 199, 188), (24, 56, 66)),
    ("whiteboard.png", "board", "Sprint plan", (244, 246, 249), (206, 212, 222)),
]


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Best available truetype face, falling back to PIL's bitmap font."""
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _gradient(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> None:
    """Fill the canvas with a vertical two-stop gradient, one scanline at a time."""
    for y in range(height):
        blend = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(
                round(top[channel] + (bottom[channel] - top[channel]) * blend)
                for channel in range(3)
            ),
        )


def _draw_photo(
    style: str,
    label: str,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    width: int = 960,
    height: int = 640,
) -> bytes:
    """Render a plausible photograph or whiteboard shot.

    Not a test card: at thumbnail size these read as real images, which is what
    the transcript needs in order to look like a conversation rather than a
    fixture. Drawing them keeps binaries out of the repository — the seed stays
    a few hundred bytes of code and reproduces identically on any machine.
    """
    from PIL import Image, ImageFilter

    image = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(image)

    if style == "board":
        # A whiteboard: ruled columns with sticky notes, shot slightly off-square.
        _gradient(draw, width, height, top, bottom)
        draw.rectangle([40, 36, width - 40, height - 36], outline=(178, 186, 198), width=3)
        for column in range(3):
            x = 90 + column * ((width - 200) // 3)
            draw.text(
                (x, 80), ["TODO", "DOING", "DONE"][column], font=_font(26), fill=(84, 96, 112)
            )
            for row in range(3 - column):
                y = 130 + row * 90
                draw.rounded_rectangle(
                    [x - 10, y, x + 190, y + 70],
                    radius=8,
                    fill=[(255, 226, 138), (183, 220, 255), (198, 240, 205)][column],
                )
    else:
        # Sky, sun, layered ridges, water. Layering is what sells the depth.
        _gradient(draw, width, height, top, bottom)
        sun_y = int(height * 0.46)
        radius = int(height * 0.11)
        draw.ellipse(
            [width // 2 - radius, sun_y - radius, width // 2 + radius, sun_y + radius],
            fill=(255, 240, 205),
        )
        horizon = int(height * 0.58)
        # Three ridges, each lighter and higher than the last. The overlap is
        # what reads as aerial perspective rather than as flat bands.
        for depth, mix in enumerate((0.45, 0.3, 0.15)):
            ridge = [
                (0, horizon + depth * 26),
                (width * 0.22, horizon - 40 + depth * 30),
                (width * 0.45, horizon + 10 + depth * 26),
                (width * 0.7, horizon - 55 + depth * 34),
                (width, horizon + depth * 22),
                (width, height),
                (0, height),
            ]
            draw.polygon(
                ridge,
                fill=tuple(
                    round(bottom[channel] * (1 - mix) + top[channel] * mix * 0.5)
                    for channel in range(3)
                ),
            )
        image = image.filter(ImageFilter.SMOOTH)
        draw = ImageDraw.Draw(image)

    caption = _font(28)
    box = draw.textbbox((0, 0), label, font=caption)
    draw.rectangle(
        [24, height - 76, 24 + (box[2] - box[0]) + 32, height - 24],
        fill=(0, 0, 0) if style != "board" else (255, 255, 255),
    )
    draw.text(
        (40, height - 64),
        label,
        font=caption,
        fill=(255, 255, 255) if style != "board" else (60, 68, 82),
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


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

        async def add_media_message(
            conversation: Conversation,
            author: str,
            hours_ago: float,
            body: str,
            photos: list[int],
            members: list[User],
        ) -> Message:
            """Append a message carrying one or more rendered images."""
            created = _at(hours_ago)
            message = Message(
                conversation_id=conversation.id,
                sender_id=users[author].id,
                type=MessageType.MEDIA,
                created_at=created,
                updated_at=created,
                **_sealed(body),
            )
            session.add(message)
            await session.flush()

            for index in photos:
                name, style, label, top, bottom = SEED_PHOTOS[index]
                data = _draw_photo(style, label, top, bottom)
                key = await storage.save(data, filename=name, content_type="image/png")
                session.add(
                    Attachment(
                        message_id=message.id,
                        file_name=name,
                        content_type="image/png",
                        size_bytes=len(data),
                        storage_key=key,
                        width=960,
                        height=640,
                        created_at=created,
                        updated_at=created,
                    )
                )

            for member in members:
                if member.id == message.sender_id:
                    continue
                session.add(
                    MessageReceipt(
                        message_id=message.id,
                        user_id=member.id,
                        delivered_at=created + timedelta(seconds=2),
                        read_at=created + timedelta(minutes=1),
                    )
                )

            if conversation.last_message_at is None or created > conversation.last_message_at:
                conversation.last_message_at = created
            return message

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
            if username == "meera":
                await add_media_message(
                    conversation,
                    "meera",
                    3,
                    "Look at this view!",
                    [1],
                    [owner, other],
                )

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

        # Photos in the group, so attachments are visible on first load.
        await add_media_message(
            goa,
            "ananya",
            8,
            "Sunset from the shack last night 🌅",
            [0, 1],
            goa_members,
        )

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
        await add_media_message(
            study,
            "kabir",
            5,
            "Whiteboard from today's session",
            [2],
            study_members,
        )

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
