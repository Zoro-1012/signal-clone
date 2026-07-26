"""Shared test fixtures.

Every test runs against its own file-backed SQLite database, created and torn
down per test. In-memory SQLite is tempting but wrong here: the async driver
hands connections between threads, and each new connection to ``:memory:`` gets
a *different* empty database, so tables vanish mid-test.

Isolation per test matters more than speed at this size — a suite where one
test's data leaks into another's assertions is worse than a slow one.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest

# Configuration is read at import time, so the environment must be set before
# anything under app.* is imported.
_TEST_DB = Path(tempfile.gettempdir()) / "signal-clone-tests"
_TEST_DB.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-signing-key-of-sufficient-length-32b")
os.environ.setdefault("UPLOAD_DIR", str(_TEST_DB / "uploads"))


@pytest.fixture
def db_path() -> Generator[Path, None, None]:
    """A unique database file per test."""
    import uuid

    path = _TEST_DB / f"{uuid.uuid4().hex}.db"
    yield path
    for suffix in ("", "-wal", "-shm", "-journal"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()


@pytest.fixture
async def app_client(db_path: Path) -> AsyncGenerator[tuple[object, object], None]:
    """A TestClient bound to a freshly created schema.

    The engine is rebuilt per test against the temporary file, and the session
    dependency is overridden rather than monkeypatched, which is the supported
    way to swap infrastructure in FastAPI and keeps production wiring untouched.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import app.models  # noqa: F401  registers every mapper
    from app.db.base import Base
    from app.db.session import get_session, get_session_factory
    from app.main import create_app

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        # Mirrors the application engine. Without it, a pooled connection left
        # behind by a WebSocket session is terminated during loop shutdown and
        # deadlocks in SQLAlchemy's greenlet bridge, hanging the test run.
        poolclass=NullPool,
    )
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def _override() -> AsyncGenerator[object, None]:
        async with factory() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_session] = _override
    # The WebSocket endpoint opens its own short sessions, so it needs the
    # factory rather than a single session. Overriding it here is what lets the
    # socket see the same temporary database as the HTTP routes.
    application.dependency_overrides[get_session_factory] = lambda: factory

    with TestClient(application) as client:
        yield client, factory

    await engine.dispose()


@pytest.fixture
async def client(app_client: tuple[object, object]) -> object:
    return app_client[0]


class Registered:
    """A registered, verified user plus the headers needed to act as them."""

    def __init__(self, user: dict[str, object], access_token: str, refresh_token: str) -> None:
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token

    @property
    def id(self) -> str:
        return str(self.user["id"])

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


def register_user(client: object, phone: str, name: str, username: str | None = None) -> Registered:
    """Drive the full onboarding flow and return an authenticated identity.

    Tests exercise the real endpoints rather than inserting rows directly, so a
    regression in registration or verification fails the tests that depend on it
    instead of being masked by a shortcut.
    """
    payload: dict[str, object] = {"phone_number": phone, "display_name": name}
    if username:
        payload["username"] = username

    response = client.post("/api/v1/auth/register", json=payload)  # type: ignore[attr-defined]
    assert response.status_code == 201, response.text
    code = response.json()["dev_code"]

    response = client.post(  # type: ignore[attr-defined]
        "/api/v1/auth/verify", json={"phone_number": phone, "code": code}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    client.cookies.clear()  # type: ignore[attr-defined]
    return Registered(body["user"], body["access_token"], body["refresh_token"])
