from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.api.deps import SettingsDep
from app.schemas.system import SystemResponse
from app.services.system_info import collect_system_info

router = APIRouter(tags=["system"])


@router.get("/system", response_model=SystemResponse)
async def system(settings: SettingsDep) -> SystemResponse:
    # Subprocess probes (nvidia-smi, ffmpeg) are blocking; keep them off the event loop.
    return await run_in_threadpool(collect_system_info, settings)
