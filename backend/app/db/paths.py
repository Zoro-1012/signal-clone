"""SQLite URL resolution.

Shared by the application engine and by Alembic. Both need the same two things
from a SQLite URL — a path anchored somewhere predictable, and a parent
directory that actually exists — and when only one of them did it, deploying
failed with ``unable to open database file`` because ``var/`` is git-ignored and
therefore absent from a fresh checkout.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import BACKEND_DIR

ASYNC_PREFIX = "sqlite+aiosqlite:///"
SYNC_PREFIX = "sqlite:///"


def resolve_sqlite_url(url: str) -> str:
    """Return ``url`` with its path anchored and its directory created.

    Relative paths resolve against ``backend/`` rather than the working
    directory, so the API, Alembic and the seeder all reach the same file no
    matter where they were launched from. Non-SQLite URLs pass through untouched.
    """
    prefix = next((p for p in (ASYNC_PREFIX, SYNC_PREFIX) if url.startswith(p)), None)
    if prefix is None:
        return url

    raw_path = url[len(prefix) :]
    # In-memory databases have no directory to create and no path to anchor.
    if raw_path.startswith(":memory:") or raw_path == "":
        return url

    path = Path(raw_path)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()

    # The directory is created here rather than assumed. It is git-ignored, so it
    # is missing on every fresh clone and on every deploy.
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{path}"
