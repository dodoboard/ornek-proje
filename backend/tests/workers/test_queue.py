from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ConflictError, NotFoundError
from app.db.base import utcnow
from app.models.enums import JobStatus
from app.models.job import Job
from app.workers.queue import JobQueue


def _get(factory: sessionmaker[Session], job_id: str) -> Job:
    with factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        return job


def test_claim_order_priority_then_fifo(queue: JobQueue) -> None:
    first = queue.enqueue("a")
    second = queue.enqueue("a")
    urgent = queue.enqueue("a", priority=5)
    claimed = [queue.claim_next("W1") for _ in range(4)]
    assert [c.id if c else None for c in claimed] == [urgent.id, first.id, second.id, None]


def test_claim_marks_running(queue: JobQueue, session_factory: sessionmaker[Session]) -> None:
    job = queue.enqueue("a", {"x": 1})
    claimed = queue.claim_next("W1")
    assert claimed is not None and claimed.payload == {"x": 1}
    stored = _get(session_factory, job.id)
    assert (stored.status, stored.worker_id, stored.attempts) == (JobStatus.RUNNING, "W1", 1)
    assert stored.started_at is not None and stored.heartbeat_at is not None


def test_cancel_queued_job_is_immediate_and_never_claimed(
    queue: JobQueue, session_factory: sessionmaker[Session]
) -> None:
    job = queue.enqueue("a")
    queue.request_cancel(job.id)
    assert _get(session_factory, job.id).status is JobStatus.CANCELLED
    assert queue.claim_next("W1") is None


def test_cancel_running_job_sets_flag(queue: JobQueue, session_factory: sessionmaker[Session]) -> None:
    job = queue.enqueue("a")
    queue.claim_next("W1")
    queue.request_cancel(job.id)
    stored = _get(session_factory, job.id)
    assert stored.status is JobStatus.RUNNING and stored.cancel_requested
    assert queue.report(job.id, progress=10) is True


def test_cancel_terminal_or_missing(queue: JobQueue) -> None:
    job = queue.enqueue("a")
    queue.claim_next("W1")
    queue.complete(job.id, {"ok": True})
    with pytest.raises(ConflictError):
        queue.request_cancel(job.id)
    with pytest.raises(NotFoundError):
        queue.request_cancel("JOB_missing")


def test_report_clamps_and_ignores_terminal(queue: JobQueue, session_factory: sessionmaker[Session]) -> None:
    job = queue.enqueue("a")
    queue.claim_next("W1")
    queue.report(job.id, status=JobStatus.ENCODING, progress=150, stage="Encoding", message="x" * 900)
    stored = _get(session_factory, job.id)
    assert (stored.status, stored.progress, stored.stage, len(stored.message or "")) == (
        JobStatus.ENCODING,
        100,
        "Encoding",
        500,
    )
    queue.fail(job.id, "GENERATION_FAILED", "boom")
    queue.report(job.id, progress=5)
    queue.complete(job.id)
    stored = _get(session_factory, job.id)
    assert (stored.status, stored.progress, stored.error_code) == (JobStatus.FAILED, 100, "GENERATION_FAILED")


def test_report_rejects_terminal_status(queue: JobQueue) -> None:
    job = queue.enqueue("a")
    with pytest.raises(ValueError):
        queue.report(job.id, status=JobStatus.COMPLETED)


def test_recover_stale_fails_orphaned_jobs(queue: JobQueue, session_factory: sessionmaker[Session]) -> None:
    stale = queue.enqueue("a")
    fresh = queue.enqueue("a")
    waiting = queue.enqueue("a")
    queue.claim_next("W1")
    queue.claim_next("W1")
    recovered = queue.recover_stale(timedelta(seconds=60), now=utcnow() + timedelta(seconds=120))
    assert set(recovered) == {stale.id, fresh.id}
    assert _get(session_factory, stale.id).error_code == "WORKER_LOST"
    assert _get(session_factory, waiting.id).status is JobStatus.QUEUED
    assert queue.recover_stale(timedelta(seconds=60)) == []
