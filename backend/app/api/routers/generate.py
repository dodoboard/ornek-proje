from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import SessionDep, SettingsDep, StorageDep
from app.core.errors import ModelMissingError, ProviderUnavailableError
from app.providers.base import ImageCapabilities, ProviderKind, ProviderStatus
from app.schemas.generation import ImageGenerateRequest
from app.schemas.job import JobRead
from app.services.image_generation import check_against_capabilities, resolve_references
from app.services.preferences import build_registry, load_preferences
from app.workers.handlers.image_generate import JOB_TYPE as IMAGE_JOB
from app.workers.queue import JobQueue

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("/image", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def generate_image(
    body: ImageGenerateRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> JobRead:
    """Validate against the selected model's capabilities, then queue an `image.generate` job."""
    prefs = load_preferences(session, settings)
    registry = build_registry(settings, prefs)
    entry = registry.entry(ProviderKind.IMAGE, body.model_key)
    info = registry.describe(entry)
    if info.status is ProviderStatus.MODEL_MISSING:
        raise ModelMissingError(info.detail)
    if info.status is not ProviderStatus.AVAILABLE:
        raise ProviderUnavailableError(info.detail or f"'{entry.key}' is not available.")

    check_against_capabilities(body, ImageCapabilities.model_validate(info.capabilities))
    resolve_references(session, storage, body)

    payload = body.model_copy(
        update={
            "model_key": entry.key,
            "watermark": prefs.ai_watermark if body.watermark is None else body.watermark,
        }
    ).model_dump(mode="json")
    job = JobQueue(request.app.state.session_factory).enqueue(IMAGE_JOB, payload, project_id=body.project_id)
    return JobRead.model_validate(job)
