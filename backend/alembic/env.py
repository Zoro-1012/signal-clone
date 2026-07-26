"""Alembic migration environment.

Runs against the synchronous SQLite driver: migrations are a short-lived,
single-threaded batch job, so the async engine would add complexity with no
benefit. The URL and the target metadata both come from the application itself,
which is what guarantees a migration can never drift from the models.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base
from app.db.types import EnumString, UTCDateTime

# Importing the models package registers every mapper on Base.metadata, which is
# what autogenerate diffs the live database against.
import app.models  # noqa: F401  isort:skip

config = context.config
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Render custom column types using their underlying SQLAlchemy type.

    Autogenerate would otherwise emit ``app.db.types.UTCDateTime()`` into the
    migration, which fails with a NameError because migrations import only
    ``sqlalchemy`` — and, more importantly, would couple a historical migration to
    application code that may be refactored or deleted later.

    ``UTCDateTime`` is a Python-side conversion over a plain DateTime column: the
    emitted DDL is identical either way, so rendering the impl is both correct and
    keeps migrations self-contained.

    Returning False delegates to Alembic's default rendering for everything else.
    """
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    if type_ == "type" and isinstance(obj, EnumString):
        return f"sa.String(length={obj.length})"
    return False


def _common_options() -> dict[str, object]:
    return {
        "target_metadata": target_metadata,
        "render_item": _render_item,
        # SQLite cannot ALTER most things in place. Batch mode rebuilds the table
        # and copies the data instead, which is what makes column and constraint
        # changes possible at all on this database.
        "render_as_batch": True,
        # Without this, a column type change is silently ignored by autogenerate.
        "compare_type": True,
        "compare_server_default": True,
    }


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting, for review or manual application."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_common_options(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_common_options())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
