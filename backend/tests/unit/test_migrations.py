from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.migrations import alembic_config


def test_models_match_migrations(migrated_db_template: Path) -> None:
    engine = create_engine(f"sqlite:///{migrated_db_template.as_posix()}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    engine.dispose()
    assert diff == []


def test_downgrade_and_upgrade_roundtrip(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'rt.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
