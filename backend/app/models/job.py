from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UTCDateTime, id_column
from app.models.enums import JobStatus, enum_column


class Job(TimestampMixin, Base):
    """Unit of background work. The `jobs` table is also the queue (claimed atomically by workers)."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
        Index("ix_jobs_queue", "status", "priority", "created_at"),
    )

    id: Mapped[str] = id_column()
    type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[JobStatus] = mapped_column(enum_column(JobStatus, "job_status"), default=JobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str | None] = mapped_column(String(120))
    message: Mapped[str | None] = mapped_column(String(500))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(40))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Worker(Base):
    """Liveness record written by each worker process."""

    __tablename__ = "workers"

    id: Mapped[str] = id_column()
    hostname: Mapped[str] = mapped_column(String(255))
    pid: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime())
    heartbeat_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    current_job_id: Mapped[str | None] = mapped_column(String(40))
    stopped_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
