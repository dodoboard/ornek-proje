from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import SessionDep, SettingsDep, StorageDep
from app.core.errors import ModelMissingError, ProviderUnavailableError
from app.models.enums import AssetRole
from app.providers.base import ImageCapabilities, ProviderKind, ProviderStatus
from app.providers.registry import ProviderInfo
from app.schemas.character import CharacterRead
from app.schemas.character_studio import (
    CharacterBibleRead,
    CharacterBibleUpdate,
    CharacterGenerateRequest,
    PromptPreview,
    SetViewRequest,
    ViewRole,
)
from app.schemas.job import JobRead
from app.services import character_studio as studio
from app.services.characters import get_character
from app.services.image_generation import check_against_capabilities, resolve_references
from app.services.preferences import build_registry, load_preferences
from app.workers.handlers.image_generate import JOB_TYPE as IMAGE_JOB
from app.workers.queue import JobQueue

router = APIRouter(prefix="/characters", tags=["character studio"])


def _image_model(session: SessionDep, settings: SettingsDep, key: str | None) -> tuple[ProviderInfo, bool]:
    prefs = load_preferences(session, settings)
    registry = build_registry(settings, prefs)
    info = registry.describe(registry.entry(ProviderKind.IMAGE, key))
    return info, prefs.ai_watermark


def _max_references(info: ProviderInfo) -> int:
    return int((info.capabilities or {}).get("max_reference_images", 0))


@router.get("/{character_id}/bible", response_model=CharacterBibleRead)
def get_bible(character_id: str, session: SessionDep) -> CharacterBibleRead:
    character = get_character(session, character_id)
    read = studio.bible_read(session, character)
    session.commit()  # persists a freshly created bible
    return read


@router.patch("/{character_id}/bible", response_model=CharacterBibleRead)
def update_bible(character_id: str, patch: CharacterBibleUpdate, session: SessionDep) -> CharacterBibleRead:
    return studio.update_bible(session, character_id, patch)


@router.post("/{character_id}/prompt-preview", response_model=PromptPreview)
def prompt_preview(
    character_id: str, body: CharacterGenerateRequest, session: SessionDep, settings: SettingsDep
) -> PromptPreview:
    """Show exactly which prompt and reference images a generation would use."""
    character = get_character(session, character_id)
    info, _ = _image_model(session, settings, body.model_key)
    return studio.preview(session, character, body, _max_references(info))


@router.post("/{character_id}/generate", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def generate(
    character_id: str,
    body: CharacterGenerateRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> JobRead:
    """Candidates → pick canonical → views → scenes, all conditioned on this character's references."""
    character = get_character(session, character_id)
    info, watermark = _image_model(session, settings, body.model_key)
    if info.status is ProviderStatus.MODEL_MISSING:
        raise ModelMissingError(info.detail)
    if info.status is not ProviderStatus.AVAILABLE:
        raise ProviderUnavailableError(info.detail or f"'{info.key}' is not available.")

    image_request = studio.build_image_request(session, character, body, _max_references(info))
    image_request = image_request.model_copy(update={"model_key": info.key, "watermark": watermark})
    check_against_capabilities(image_request, ImageCapabilities.model_validate(info.capabilities))
    resolve_references(session, storage, image_request)
    session.commit()

    job = JobQueue(request.app.state.session_factory).enqueue(
        IMAGE_JOB, image_request.model_dump(mode="json"), project_id=body.project_id
    )
    return JobRead.model_validate(job)


@router.put("/{character_id}/views/{role}", response_model=CharacterRead)
def set_view(character_id: str, role: ViewRole, body: SetViewRequest, session: SessionDep) -> CharacterRead:
    """Use an image as the canonical portrait or a front / 3/4 / full-body view."""
    character = studio.set_view(session, character_id, AssetRole(role), body.asset_id)
    return CharacterRead.model_validate(character)
