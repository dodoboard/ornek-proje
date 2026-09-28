from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import PaginationDep, SessionDep, SettingsDep
from app.models.enums import JobStatus
from app.models.job import Job
from app.schemas.common import Page
from app.schemas.job import JobRead
from app.services import jobs as service
from app.workers.queue import JobQueue

router = APIRouter(prefix="/jobs", tags=["jobs"])

SSE_KEEPALIVE_S = 15.0
SSE_RETRY_MS = 2000


@router.get("", response_model=Page[JobRead])
def list_jobs(
    session: SessionDep,
    page: PaginationDep,
    status_filter: Annotated[list[JobStatus] | None, Query(alias="status")] = None,
    active: bool | None = None,
    type: Annotated[str | None, Query(max_length=60)] = None,
    project_id: Annotated[str | None, Query(max_length=40)] = None,
) -> Page[JobRead]:
    items, total = service.list_jobs(
        session,
        statuses=status_filter,
        active=active,
        job_type=type,
        project_id=project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=[JobRead.model_validate(j) for j in items], total=total, **page.__dict__)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: SessionDep) -> JobRead:
    return JobRead.model_validate(service.get_job(session, job_id))


@router.delete("/{job_id}", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def cancel_job(job_id: str, request: Request) -> JobRead:
    """Cancel a job. Queued jobs stop immediately; running jobs stop at the next safe point."""
    queue = JobQueue(request.app.state.session_factory)
    queue.request_cancel(job_id)
    with request.app.state.session_factory() as session:
        return JobRead.model_validate(service.get_job(session, job_id))


def _load(factory: sessionmaker[Session], job_id: str) -> JobRead | None:
    with factory() as session:
        job = session.get(Job, job_id)
        return None if job is None else JobRead.model_validate(job)


@router.get(
    "/{job_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Server-Sent Events: `job`"}},
)
async def job_events(
    job_id: str, request: Request, session: SessionDep, settings: SettingsDep
) -> StreamingResponse:
    service.get_job(session, job_id)  # 404 before opening the stream
    session.close()
    factory: sessionmaker[Session] = request.app.state.session_factory

    async def stream() -> AsyncIterator[str]:
        yield f"retry: {SSE_RETRY_MS}\n\n"
        last_payload: str | None = None
        last_sent = time.monotonic()
        while not await request.is_disconnected():
            job = await run_in_threadpool(_load, factory, job_id)
            if job is None:
                yield 'event: error\ndata: {"code": "NOT_FOUND"}\n\n'
                return
            payload = job.model_dump_json()
            if payload != last_payload:
                yield f"event: job\ndata: {payload}\n\n"
                last_payload, last_sent = payload, time.monotonic()
            if job.status.is_terminal:
                return
            if time.monotonic() - last_sent > SSE_KEEPALIVE_S:
                yield ": keep-alive\n\n"
                last_sent = time.monotonic()
            await asyncio.sleep(settings.sse_poll_interval_s)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
