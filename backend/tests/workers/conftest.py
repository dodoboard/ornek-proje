from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.session import create_db_engine, create_session_factory
from app.workers.queue import JobQueue
from app.workers.registry import HandlerRegistry
from app.workers.runner import Worker


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    assert settings.database_url is not None
    eng = create_db_engine(settings.database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def queue(session_factory: sessionmaker[Session]) -> JobQueue:
    return JobQueue(session_factory)


@pytest.fixture
def registry() -> HandlerRegistry:
    return HandlerRegistry()


@pytest.fixture
def worker(settings: Settings, queue: JobQueue, registry: HandlerRegistry) -> Iterator[Worker]:
    settings.job_progress_min_interval_s = 0
    w = Worker(settings, queue, registry)
    queue.register_worker(w.worker_id, "test", 1)
    yield w
    w.stop_event.set()
