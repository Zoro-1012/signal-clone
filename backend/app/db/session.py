"""Async engine, session factory and the request-scoped session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logging import get_logger
from app.db.paths import resolve_sqlite_url

logger = get_logger(__name__)


DATABASE_URL = resolve_sqlite_url(settings.database_url)

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.db_echo,
    future=True,
    # SQLite refuses cross-thread connection reuse by default; the async driver
    # legitimately hands connections between threads in its executor pool.
    connect_args={"check_same_thread": False} if _IS_SQLITE else {},
    # NullPool for SQLite: open a connection per checkout and close it on release.
    #
    # This is a correctness fix, not a tuning choice. A pooled aiosqlite
    # connection that outlives its session is terminated by the pool during
    # shutdown, and that termination runs through SQLAlchemy's greenlet bridge —
    # which cannot complete once the event loop is already closing. The process
    # then hangs on exit instead of stopping. Long-lived WebSocket tasks make
    # this likely, because they open sessions outside the request lifecycle.
    #
    # The cost is negligible here: opening a SQLite connection is cheap, and WAL
    # mode means concurrency is governed by the file, not by the pool.
    poolclass=NullPool if _IS_SQLITE else None,
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


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory itself, rather than a single session.

    A WebSocket connection lives for minutes or hours, so it cannot hold one
    session open for its lifetime — that would pin a connection and keep a
    transaction alive across unrelated work. It instead opens a short session per
    operation, which means it needs the *factory*.

    Exposed as a dependency rather than imported directly so tests can point the
    socket at their own database through the same override mechanism the HTTP
    routes use. Reaching for the module-level factory would make the endpoint
    untestable by construction.
    """
    return SessionFactory


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
