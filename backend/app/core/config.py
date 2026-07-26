"""Application configuration.

All runtime configuration is funnelled through a single ``Settings`` object so
that no module ever reads ``os.environ`` directly. That keeps configuration
discoverable (one file lists everything the app can be tuned with), typed
(Pydantic validates at startup rather than failing at first use), and testable
(tests override the cached accessor instead of mutating the environment).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/  — the directory containing app/, used to anchor relative paths so the
# server behaves identically regardless of the working directory it is booted from.
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Sentinel signing key. Deliberately not a valid secret — production boot rejects it
# (see Settings._reject_default_secret_in_production), so it can never ship.
# Bandit's hardcoded-credential rule is suppressed here for exactly that reason.
DEFAULT_JWT_SECRET = "dev-only-secret-do-not-use-in-production"  # noqa: S105

# RFC 7518 requires an HMAC key at least the length of the hash output (32 bytes
# for SHA-256). PyJWT only warns about shorter keys, so this is enforced at boot.
MIN_JWT_SECRET_BYTES = 32
# Not a credential: the shell command an operator runs to mint one.
_SECRET_RECIPE = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'  # noqa: S105


class Settings(BaseSettings):
    """Typed, validated application settings sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Application -----------------------------------------------------
    app_name: str = "Signal Clone API"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    public_base_url: str = "http://localhost:8000"

    # ---- Database --------------------------------------------------------
    # SQLite is mandated by the brief. The async driver keeps database I/O off
    # the event loop's critical path, matching the async request handlers.
    database_url: str = "sqlite+aiosqlite:///./var/signal.db"
    db_echo: bool = False

    # ---- Authentication --------------------------------------------------
    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30

    # ---- Mocked verification --------------------------------------------
    # The brief explicitly permits mocked phone verification. The code is fixed,
    # but expiry, attempt limits and single-use consumption are still enforced so
    # the flow exercises the same paths a real provider would.
    mock_otp_code: str = "123456"
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5

    # ---- Simulated encryption -------------------------------------------
    # Real E2EE is out of scope (see PROJECT.md §3.5). This identifies which
    # mock cipher sealed a payload, so the column means something the day a real
    # implementation is swapped in.
    encryption_key_id: str = "mock-key-v1"

    # ---- Uploads ---------------------------------------------------------
    upload_dir: Path = BACKEND_DIR / "var" / "uploads"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MiB
    allowed_upload_types: list[str] = Field(
        default_factory=lambda: [
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "application/pdf",
            "text/plain",
        ]
    )

    # ---- CORS ------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ---- Real-time -------------------------------------------------------
    ws_heartbeat_seconds: int = 25
    typing_timeout_seconds: int = 6
    disappearing_sweep_seconds: int = 30

    @field_validator("cors_origins", "allowed_upload_types", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        """Allow list settings to be supplied as ``a,b,c`` in a .env file.

        Twelve-factor environments only carry strings, so a comma-separated form
        has to be accepted alongside the JSON list Pydantic expects natively.
        """
        if isinstance(value, str):
            if value.startswith("["):
                return value
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> Settings:
        """Refuse to boot a production process with the placeholder signing key.

        A misconfigured deployment that silently starts with a publicly known JWT
        secret would let anyone mint valid sessions. Failing loudly at startup is
        the only safe behaviour: the failure is immediate, obvious and impossible
        to overlook, whereas the vulnerability would be silent.
        """
        if self.environment != "production":
            return self

        if self.jwt_secret_key == DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a unique value in production. "
                f"Generate one with: {_SECRET_RECIPE}"
            )
        # RFC 7518 §3.2: an HMAC key for HS256 must be at least as long as the
        # hash output. A shorter key weakens the signature, and PyJWT only warns.
        if len(self.jwt_secret_key.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_BYTES} bytes for "
                f"{self.jwt_algorithm}. Generate one with: {_SECRET_RECIPE}"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sync_database_url(self) -> str:
        """Blocking equivalent of ``database_url``, for Alembic migrations.

        Alembic runs outside the event loop, so it needs the sync driver.
        """
        return self.database_url.replace("+aiosqlite", "")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached because settings are immutable for the lifetime of the process, and
    because FastAPI resolves this as a dependency on many requests.
    """
    return Settings()


settings = get_settings()
