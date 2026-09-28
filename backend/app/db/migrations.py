from __future__ import annotations

import time

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.core.config import BACKEND_DIR


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


def upgrade_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


def is_at_head(database_url: str) -> bool:
    heads = set(ScriptDirectory.from_config(alembic_config(database_url)).get_heads())
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            current = set(MigrationContext.configure(conn).get_current_heads())
    finally:
        engine.dispose()
    return current == heads


def wait_for_schema(database_url: str, timeout_s: float = 60.0, poll_s: float = 1.0) -> None:
    """Block until the API process has applied migrations (avoids two processes migrating at once)."""
    deadline = time.monotonic() + timeout_s
    while not is_at_head(database_url):
        if time.monotonic() > deadline:
            raise RuntimeError(
                "Database schema is not up to date. Run `alembic upgrade head` or start the API."
            )
        time.sleep(poll_s)
