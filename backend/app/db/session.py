"""Async engine, session factory and the request-scoped session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import BACKEND_DIR, settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _resolve_sqlite_path(url: str) -> str:
    """Anchor relative SQLite paths to backend/ and ensure the directory exists.

    Without this, ``sqlite:///./var/signal.db`` resolves against whatever
    directory the process happened to start in, so the API and the seed script
    can silently end up using two different database files.
    """
    marker = "sqlite+aiosqlite:///"
    if not url.startswith(marker):
        return url
    raw_path = url[len(marker) :]
    if raw_path == ":memory:" or raw_path.startswith(":memory:"):
        return url
    path = Path(raw_path)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"{marker}{path}"


DATABASE_URL = _resolve_sqlite_path(settings.database_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.db_echo,
    future=True,
    # SQLite refuses cross-thread connection reuse by default; the async driver
    # legitimately hands connections between threads in its executor pool.
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

# expire_on_commit=False: without it, every attribute access after commit triggers
# a fresh SELECT. Response serialisation happens after the commit, so leaving the
# default on would issue a lazy-load storm — and raise MissingGreenlet under async.
SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection: Any, _: Any) -> None:
    """Apply the SQLite pragmas this workload needs, on every new connection.

    - ``foreign_keys=ON``  — SQLite ignores foreign keys unless asked. Our cascade
      rules are load-bearing, so this is not optional.
    - ``journal_mode=WAL`` — readers no longer block on the writer, which is what
      makes a single-writer chat backend viable on SQLite at all.
    - ``synchronous=NORMAL`` — with WAL this is durable across process crashes and
      removes an fsync from every commit.
    - ``busy_timeout``     — wait out a concurrent writer instead of failing fast
      with "database is locked".

    WAL requires shared-memory locking, which some filesystems (network mounts,
    certain container bind mounts) do not implement. Rather than refuse to boot,
    fall back to the rollback journal and say so loudly: correctness is preserved,
    only read/write concurrency is reduced.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception:  # any driver-level error here means WAL is unavailable
            logger.warning(
                "sqlite_wal_unavailable",
                extra={"detail": "falling back to rollback journal; concurrency reduced"},
            )
            cursor.execute("PRAGMA journal_mode=DELETE")
            cursor.execute("PRAGMA synchronous=FULL")
    finally:
        cursor.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped session.

    One transaction per request. The session is closed on the way out whatever
    happens; rollback on error is handled by the session's context manager, and
    services own their own commits so the transaction boundary is explicit and
    visible where the business rule lives.
    """
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close the pool on shutdown so the process exits cleanly."""
    await engine.dispose()
