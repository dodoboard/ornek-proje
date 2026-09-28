from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import JobStatus
from app.models.job import Job
from app.workers.handlers.diagnostics import JOB_TYPE, run_diagnostics
from app.workers.queue import JobQueue
from app.workers.registry import HandlerRegistry, default_registry
from app.workers.runner import Worker
from tests.conftest import requires_ffmpeg


def test_default_registry_has_diagnostics() -> None:
    assert JOB_TYPE in default_registry().types()


@requires_ffmpeg
def test_diagnostics_runs_real_encode(
    worker: Worker, queue: JobQueue, registry: HandlerRegistry, session_factory: sessionmaker[Session]
) -> None:
    registry.register(JOB_TYPE, run_diagnostics)
    job = queue.enqueue(JOB_TYPE)
    worker.run_once()
    with session_factory() as session:
        stored = session.get(Job, job.id)
    assert stored is not None
    assert stored.status is JobStatus.COMPLETED, stored.error_message
    checks = stored.result["checks"]  # type: ignore[index]
    assert checks["storage"]["status"] == "ok"
    assert checks["ffmpeg"]["status"] == "ok"
    assert checks["ffmpeg"]["bytes"] > 0
    assert checks["gpu"]["status"] in {"ok", "missing", "error"}
