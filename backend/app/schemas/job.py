from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.enums import JobStatus
from app.schemas.common import TimestampedRead


class JobRead(TimestampedRead):
    type: str
    status: JobStatus
    progress: int
    stage: str | None
    message: str | None
    error_code: str | None
    error_message: str | None
    result: dict[str, Any] | None
    cancel_requested: bool
    attempts: int
    project_id: str | None
    started_at: datetime | None
    finished_at: datetime | None


class WorkerStatus(BaseModel):
    status: Literal["online", "offline"]
    worker_id: str | None = None
    heartbeat_at: datetime | None = None
    current_job_id: str | None = None
