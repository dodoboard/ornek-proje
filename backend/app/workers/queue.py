"""SQLite-backed job queue. Every method uses its own short transaction (safe across processes/threads).

PostgreSQL migration note: `claim_next` would use `SELECT ... FOR UPDATE SKIP LOCKED`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.ids import IdPrefix, new_id
from app.db.base import utcnow
from app.models.enums import TERMINAL_JOB_STATUSES, JobStatus
from app.models.job import Job, Worker

ACTIVE_STATUSES = tuple(s for s in JobStatus if s.is_active)
MESSAGE_MAX = 500


@dataclass(frozen=True)
class ClaimedJob:
    id: str
    type: str
    payload: dict[str, Any]
    project_id: str | None


class JobQueue:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    # ------------------------------------------------------------------ producer side

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        project_id: str | None = None,
        priority: int = 0,
    ) -> Job:
        with self._sessions.begin() as session:
            job = Job(
                id=new_id(IdPrefix.JOB),
                type=job_type,
                status=JobStatus.QUEUED,
                progress=0,
                payload=payload or {},
                project_id=project_id,
                priority=priority,
                cancel_requested=False,
                attempts=0,
            )
            session.add(job)
        return job

    def request_cancel(self, job_id: str) -> Job:
        """Queued jobs are cancelled immediately; running jobs are flagged for the worker.

        Uses conditional UPDATEs so it cannot race with a worker claiming the same job.
        """
        now = utcnow()
        with self._sessions.begin() as session:
            cancelled_now = cast(
                CursorResult[Any],
                session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
                    .values(
                        status=JobStatus.CANCELLED,
                        cancel_requested=True,
                        finished_at=now,
                        updated_at=now,
                        message="Cancelled before start.",
                    )
                    .execution_options(synchronize_session=False)
                ),
            )
            flagged = cancelled_now.rowcount
            if flagged == 0:
                flagged = cast(
                    CursorResult[Any],
                    session.execute(
                        update(Job)
                        .where(Job.id == job_id, Job.status.in_(ACTIVE_STATUSES))
                        .values(cancel_requested=True, updated_at=now)
                        .execution_options(synchronize_session=False)
                    ),
                ).rowcount
            job = session.get(Job, job_id)
            if job is None:
                raise NotFoundError("Job not found.")
            if flagged == 0:
                raise ConflictError(f"Job is already {job.status.value}.")
        return job

    # ------------------------------------------------------------------ worker side

    def claim_next(self, worker_id: str) -> ClaimedJob | None:
        now = utcnow()
        next_id = (
            select(Job.id)
            .where(Job.status == JobStatus.QUEUED, Job.cancel_requested.is_(False))
            .order_by(Job.priority.desc(), Job.created_at, Job.id)
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            update(Job)
            .where(Job.id == next_id, Job.status == JobStatus.QUEUED)
            .values(
                status=JobStatus.RUNNING,
                worker_id=worker_id,
                started_at=now,
                heartbeat_at=now,
                updated_at=now,
                attempts=Job.attempts + 1,
                stage="Starting",
            )
            .returning(Job.id, Job.type, Job.payload, Job.project_id)
            .execution_options(synchronize_session=False)
        )
        with self._sessions.begin() as session:
            row = session.execute(stmt).first()
        if row is None:
            return None
        return ClaimedJob(
            id=row.id, type=row.type, payload=dict(row.payload or {}), project_id=row.project_id
        )

    def report(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: int | None = None,
        stage: str | None = None,
        message: str | None = None,
    ) -> bool:
        """Persist progress; returns True if cancellation was requested."""
        values: dict[str, Any] = {"heartbeat_at": utcnow(), "updated_at": utcnow()}
        if status is not None:
            if status.is_terminal or status is JobStatus.QUEUED:
                raise ValueError("use complete/fail/cancel for terminal states")
            values["status"] = status
        if progress is not None:
            values["progress"] = max(0, min(100, int(progress)))
        if stage is not None:
            values["stage"] = stage[:120]
        if message is not None:
            values["message"] = message[:MESSAGE_MAX]
        with self._sessions.begin() as session:
            session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status.not_in(TERMINAL_JOB_STATUSES))
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            return bool(session.scalar(select(Job.cancel_requested).where(Job.id == job_id)))

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._sessions() as session:
            return bool(session.scalar(select(Job.cancel_requested).where(Job.id == job_id)))

    def complete(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        self._finish(job_id, JobStatus.COMPLETED, progress=100, result=result or {}, stage="Done")

    def fail(self, job_id: str, code: ErrorCode | str, message: str) -> None:
        self._finish(job_id, JobStatus.FAILED, error_code=str(code), error_message=message[:2000])

    def mark_cancelled(self, job_id: str, message: str = "Cancelled by user.") -> None:
        self._finish(job_id, JobStatus.CANCELLED, message=message)

    def _finish(self, job_id: str, status: JobStatus, **values: Any) -> None:
        now = utcnow()
        with self._sessions.begin() as session:
            session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status.not_in(TERMINAL_JOB_STATUSES))
                .values(status=status, finished_at=now, updated_at=now, heartbeat_at=now, **values)
                .execution_options(synchronize_session=False)
            )

    def recover_stale(self, stale_after: timedelta, now: datetime | None = None) -> list[str]:
        """Fail running jobs whose worker stopped heart-beating (crash, kill, power loss)."""
        cutoff = (now or utcnow()) - stale_after
        with self._sessions.begin() as session:
            ids = list(
                session.scalars(
                    select(Job.id).where(Job.status.in_(ACTIVE_STATUSES), Job.heartbeat_at < cutoff)
                )
            )
            if ids:
                session.execute(
                    update(Job)
                    .where(Job.id.in_(ids))
                    .values(
                        status=JobStatus.FAILED,
                        error_code=ErrorCode.WORKER_LOST.value,
                        error_message="The worker stopped responding. Please retry the job.",
                        finished_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    .execution_options(synchronize_session=False)
                )
        return ids

    # ------------------------------------------------------------------ worker liveness

    def register_worker(self, worker_id: str, hostname: str, pid: int) -> None:
        now = utcnow()
        with self._sessions.begin() as session:
            session.add(Worker(id=worker_id, hostname=hostname, pid=pid, started_at=now, heartbeat_at=now))

    def worker_heartbeat(self, worker_id: str, current_job_id: str | None) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(Worker)
                .where(Worker.id == worker_id)
                .values(heartbeat_at=utcnow(), current_job_id=current_job_id)
                .execution_options(synchronize_session=False)
            )
            if current_job_id is not None:
                session.execute(
                    update(Job)
                    .where(Job.id == current_job_id, Job.status.in_(ACTIVE_STATUSES))
                    .values(heartbeat_at=utcnow())
                    .execution_options(synchronize_session=False)
                )

    def stop_worker(self, worker_id: str) -> None:
        with self._sessions.begin() as session:
            session.execute(
                update(Worker)
                .where(Worker.id == worker_id)
                .values(stopped_at=utcnow(), current_job_id=None)
                .execution_options(synchronize_session=False)
            )
