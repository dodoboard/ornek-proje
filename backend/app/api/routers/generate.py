from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import SessionDep, SettingsDep, StorageDep
from app.core.errors import ModelMissingError, NotFoundError, ProviderUnavailableError, UnsupportedFormatError
from app.models.enums import AssetKind
from app.models.script import Shot
from app.providers.base import ImageCapabilities, ProviderKind, ProviderStatus, VideoCapabilities
from app.schemas.generation import ImageEditRequest, ImageGenerateRequest
from app.schemas.job import JobRead
from app.schemas.video import VideoGenerateRequest
from app.services.assets import get_asset
from app.services.image_generation import (
    check_against_capabilities,
    check_edit_against_capabilities,
    image_path,
    resolve_references,
)
from app.services.model_selection import require_available
from app.services.preferences import build_registry, load_preferences
from app.services.video_generation import check_video_against_capabilities
from app.workers.handlers.image_edit import JOB_TYPE as EDIT_JOB
from app.workers.handlers.image_generate import JOB_TYPE as IMAGE_JOB
from app.workers.handlers.video_generate import JOB_TYPE as VIDEO_JOB
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


@router.post("/image-edit", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def edit_image(
    body: ImageEditRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> JobRead:
    """Instruction edit, inpaint (mask: white = change) or outpaint an existing image asset."""
    prefs = load_preferences(session, settings)
    registry = build_registry(settings, prefs)
    entry = registry.entry(ProviderKind.IMAGE, body.model_key)
    info = registry.describe(entry)
    if info.status is ProviderStatus.MODEL_MISSING:
        raise ModelMissingError(info.detail)
    if info.status is not ProviderStatus.AVAILABLE:
        raise ProviderUnavailableError(info.detail or f"'{entry.key}' is not available.")

    source = get_asset(session, body.source_asset_id)
    if source.kind is not AssetKind.IMAGE or not source.width or not source.height:
        raise UnsupportedFormatError("The source must be an image.")
    caps = ImageCapabilities.model_validate(info.capabilities)
    check_edit_against_capabilities(body, caps, (source.width, source.height))
    if body.mask_asset_id:
        image_path(session, storage, body.mask_asset_id, "mask")
    resolve_references(session, storage, body)

    payload = body.model_copy(
        update={
            "model_key": entry.key,
            "watermark": prefs.ai_watermark if body.watermark is None else body.watermark,
        }
    ).model_dump(mode="json")
    job = JobQueue(request.app.state.session_factory).enqueue(EDIT_JOB, payload, project_id=body.project_id)
    return JobRead.model_validate(job)


@router.post("/video", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def generate_video(
    body: VideoGenerateRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> JobRead:
    """Image-to-video / text-to-video with the local video model, or camera motion without AI."""
    registry = build_registry(settings, load_preferences(session, settings))
    info = require_available(registry, ProviderKind.VIDEO, body.model_key)
    check_video_against_capabilities(body, VideoCapabilities.model_validate(info.capabilities))
    for asset_id, label in ((body.image_asset_id, "start image"), (body.last_image_asset_id, "last image")):
        if asset_id:
            image_path(session, storage, asset_id, label)
    resolve_references(session, storage, body)
    if body.shot_id and session.get(Shot, body.shot_id) is None:
        raise NotFoundError("Shot not found.")
    payload = body.model_copy(update={"model_key": info.key}).model_dump(mode="json")
    job = JobQueue(request.app.state.session_factory).enqueue(VIDEO_JOB, payload, project_id=body.project_id)
    return JobRead.model_validate(job)
