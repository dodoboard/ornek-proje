from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import EffectiveSettingsDep, SessionDep
from app.schemas.job import JobRead
from app.schemas.system import SystemResponse
from app.services.jobs import worker_status
from app.services.system_info import collect_system_info
from app.workers.handlers.diagnostics import JOB_TYPE as DIAGNOSTICS_JOB
from app.workers.queue import JobQueue

router = APIRouter(tags=["system"])


@router.get("/system", response_model=SystemResponse)
async def system(settings: EffectiveSettingsDep, session: SessionDep) -> SystemResponse:
    # Subprocess probes (nvidia-smi, ffmpeg) are blocking; keep them off the event loop.
    info = await run_in_threadpool(collect_system_info, settings)
    info.worker = await run_in_threadpool(worker_status, session, settings)
    return info


@router.post("/system/diagnostics", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def run_diagnostics(request: Request) -> JobRead:
    """Queue a worker self-test (storage, disk, FFmpeg encode, GPU driver, ML packages)."""
    job = JobQueue(request.app.state.session_factory).enqueue(DIAGNOSTICS_JOB)
    return JobRead.model_validate(job)
