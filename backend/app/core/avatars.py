"""Deterministic avatar colours.

Signal gives every contact without a photo a coloured circle holding their
initials. The colour has to be stable — the same person must look the same on
every device and after every reinstall — so it is derived from an immutable
property of the account rather than chosen at random or at render time.
"""

from __future__ import annotations

import hashlib

# Signal's own palette names, kept as tokens rather than hex values so the
# frontend owns the actual colours and light/dark variants.
AVATAR_COLORS: tuple[str, ...] = (
    "ultramarine",
    "crimson",
    "vermilion",
    "burlap",
    "forest",
    "wintergreen",
    "teal",
    "blue",
    "indigo",
    "violet",
    "plum",
    "taupe",
    "steel",
)


def pick_avatar_color(seed: str) -> str:
    """Map a stable seed (a phone number) onto a palette entry.

    SHA-256 rather than ``hash()``: Python randomises string hashing per process,
    so the built-in would hand the same user a different colour after any restart.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return AVATAR_COLORS[digest[0] % len(AVATAR_COLORS)]


def initials(display_name: str) -> str:
    """Derive the one or two letters shown inside the circle."""
    parts = [part for part in display_name.strip().split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
