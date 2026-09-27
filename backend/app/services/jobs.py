from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import utcnow
from app.models.enums import JobStatus
from app.models.job import Job, Worker
from app.schemas.job import WorkerStatus
from app.services.crud import get_or_404, paginate
from app.workers.queue import ACTIVE_STATUSES


def list_jobs(
    session: Session,
    *,
    statuses: Sequence[JobStatus] | None,
    active: bool | None,
    job_type: str | None,
    project_id: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Job], int]:
    stmt = select(Job).order_by(Job.created_at.desc(), Job.id.desc())
    if statuses:
        stmt = stmt.where(Job.status.in_(statuses))
    if active is True:
        stmt = stmt.where(Job.status.in_((JobStatus.QUEUED, *ACTIVE_STATUSES)))
    elif active is False:
        stmt = stmt.where(Job.status.in_([s for s in JobStatus if s.is_terminal]))
    if job_type:
        stmt = stmt.where(Job.type == job_type)
    if project_id:
        stmt = stmt.where(Job.project_id == project_id)
    return paginate(session, stmt, limit, offset)


def get_job(session: Session, job_id: str) -> Job:
    return get_or_404(session, Job, job_id, "Job")


def worker_status(session: Session, settings: Settings) -> WorkerStatus:
    worker = session.scalar(
        select(Worker).where(Worker.stopped_at.is_(None)).order_by(Worker.heartbeat_at.desc()).limit(1)
    )
    if worker is None:
        return WorkerStatus(status="offline")
    fresh_after = utcnow() - timedelta(seconds=settings.worker_heartbeat_interval_s * 3)
    online = worker.heartbeat_at >= fresh_after
    return WorkerStatus(
        status="online" if online else "offline",
        worker_id=worker.id,
        heartbeat_at=worker.heartbeat_at,
        current_job_id=worker.current_job_id if online else None,
        runtime=worker.runtime,
    )
