from __future__ import annotations

import sys
import threading
import time
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import VramOutOfMemoryError
from app.models.enums import JobStatus
from app.models.job import Job
from app.workers.context import JobContext
from app.workers.queue import JobQueue
from app.workers.registry import HandlerRegistry
from app.workers.runner import GENERIC_FAILURE, Worker


def _get(factory: sessionmaker[Session], job_id: str) -> Job:
    with factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        return job


def test_success_records_result_and_cleans_temp(
    worker: Worker, queue: JobQueue, registry: HandlerRegistry, session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:  # fmt: skip
    seen: dict[str, Any] = {}

    def handler(ctx: JobContext) -> dict[str, Any]:
        (ctx.temp_dir / "scratch.txt").write_text("x")
        seen["temp"] = ctx.temp_dir
        ctx.report(40, status=JobStatus.GENERATING_IMAGE, stage="Rendering")
        return {"answer": 42, "payload": ctx.payload}

    registry.register("ok", handler)
    job = queue.enqueue("ok", {"n": 1})
    assert worker.run_once() is True

    stored = _get(session_factory, job.id)
    assert stored.status is JobStatus.COMPLETED
    assert stored.progress == 100
    assert stored.result == {"answer": 42, "payload": {"n": 1}}
    assert stored.finished_at is not None
    assert not seen["temp"].exists()
    assert worker.run_once() is False


def test_app_error_is_reported_with_code(
    worker: Worker, queue: JobQueue, registry: HandlerRegistry, session_factory: sessionmaker[Session]
) -> None:
    def handler(ctx: JobContext) -> dict[str, Any]:
        raise VramOutOfMemoryError()

    registry.register("oom", handler)
    job = queue.enqueue("oom")
    worker.run_once()
    stored = _get(session_factory, job.id)
    assert (stored.status, stored.error_code) == (JobStatus.FAILED, "VRAM_OOM")


def test_unexpected_error_hides_details(
    worker: Worker, queue: JobQueue, registry: HandlerRegistry, session_factory: sessionmaker[Session]
) -> None:
    def handler(ctx: JobContext) -> dict[str, Any]:
        raise RuntimeError("secret /home/user/path")

    registry.register("boom", handler)
    job = queue.enqueue("boom")
    worker.run_once()
    stored = _get(session_factory, job.id)
    assert stored.error_code == "GENERATION_FAILED"
    assert stored.error_message == GENERIC_FAILURE


def test_unknown_job_type_fails(
    worker: Worker, queue: JobQueue, session_factory: sessionmaker[Session]
) -> None:
    job = queue.enqueue("nope")
    worker.run_once()
    assert _get(session_factory, job.id).error_code == "VALIDATION_ERROR"


def test_cooperative_cancel_mid_job(
    worker: Worker, queue: JobQueue, registry: HandlerRegistry, session_factory: sessionmaker[Session]
) -> None:
    started = threading.Event()
    steps: list[int] = []

    def handler(ctx: JobContext) -> dict[str, Any]:
        started.set()
        for i in range(200):
            steps.append(i)
            ctx.report(i / 2)
            time.sleep(0.01)
        return {}

    registry.register("long", handler)
    job = queue.enqueue("long")
    runner = threading.Thread(target=worker.run_once)
    runner.start()
    assert started.wait(5)
    queue.request_cancel(job.id)
    runner.join(10)

    stored = _get(session_factory, job.id)
    assert stored.status is JobStatus.CANCELLED
    assert len(steps) < 200


def test_cancel_terminates_subprocess(
    worker: Worker, queue: JobQueue, registry: HandlerRegistry, session_factory: sessionmaker[Session]
) -> None:
    started = threading.Event()

    def handler(ctx: JobContext) -> dict[str, Any]:
        started.set()
        ctx.run_subprocess([sys.executable, "-c", "import time; time.sleep(60)"])
        return {}

    registry.register("proc", handler)
    job = queue.enqueue("proc")
    t0 = time.monotonic()
    runner = threading.Thread(target=worker.run_once)
    runner.start()
    assert started.wait(5)
    time.sleep(0.3)
    queue.request_cancel(job.id)
    runner.join(15)

    assert not runner.is_alive()
    assert time.monotonic() - t0 < 15
    assert _get(session_factory, job.id).status is JobStatus.CANCELLED


def test_worker_stop_marks_job_failed_worker_stopped(
    worker: Worker, queue: JobQueue, registry: HandlerRegistry, session_factory: sessionmaker[Session]
) -> None:
    def handler(ctx: JobContext) -> dict[str, Any]:
        worker.stop()
        ctx.report(50)
        return {}

    registry.register("stop", handler)
    job = queue.enqueue("stop")
    worker.run_once()
    assert _get(session_factory, job.id).error_code == "WORKER_STOPPED"


def test_subprocess_rejects_shell_string(worker: Worker, queue: JobQueue, registry: HandlerRegistry,
                                         session_factory: sessionmaker[Session]) -> None:  # fmt: skip
    def handler(ctx: JobContext) -> dict[str, Any]:
        ctx.run_subprocess("echo hi; rm -rf /")  # type: ignore[arg-type]
        return {}

    registry.register("shell", handler)
    job = queue.enqueue("shell")
    worker.run_once()
    assert _get(session_factory, job.id).status is JobStatus.FAILED


def test_report_throttling(queue: JobQueue, settings: Settings) -> None:
    job = queue.enqueue("a")
    queue.claim_next("W1")
    calls: list[int | None] = []
    original = queue.report

    def spy(job_id: str, **kwargs: Any) -> bool:
        calls.append(kwargs.get("progress"))
        return original(job_id, **kwargs)

    queue.report = spy  # type: ignore[method-assign]
    now = [0.0]
    ctx = JobContext(
        job_id=job.id, job_type="a", payload={}, project_id=None, queue=queue,
        temp_root=settings.data_path("temp", "jobs"), stop_event=threading.Event(),
        min_report_interval_s=1.0, clock=lambda: now[0],
    )  # fmt: skip
    ctx.report(1)
    ctx.report(2)
    ctx.report(3, stage="New stage")
    now[0] = 2.0
    ctx.report(4)
    assert calls == [1, 3, 4]
    ctx.cleanup()


@pytest.mark.parametrize("fraction", [-1, 0, 0.5, 1, 2])
def test_stage_progress_maps_into_range(queue: JobQueue, settings: Settings, fraction: float) -> None:
    job = queue.enqueue("a")
    queue.claim_next("W1")
    ctx = JobContext(
        job_id=job.id, job_type="a", payload={}, project_id=None, queue=queue,
        temp_root=settings.data_path("temp", "jobs"), stop_event=threading.Event(), min_report_interval_s=0,
    )  # fmt: skip
    ctx.stage_progress(20, 60)(fraction)
    with queue._sessions() as session:
        progress = session.get(Job, job.id).progress  # type: ignore[union-attr]
    assert progress == round(20 + 40 * min(1, max(0, fraction)))
    ctx.cleanup()
