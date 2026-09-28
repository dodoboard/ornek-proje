"""Shared validation for image generation (used by the API before queueing and by the worker)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode, NotFoundError, UnsupportedFormatError
from app.models.character import Character
from app.models.enums import AssetKind, ConsentSubject
from app.models.project import Project
from app.providers.base import ImageCapabilities
from app.schemas.generation import ImageEditRequest, ImageGenerateRequest
from app.services.assets import get_asset
from app.services.consents import require_active_consent
from app.services.storage import StorageService


class InvalidGenerationRequestError(AppError):
    code = ErrorCode.INVALID_GENERATION_REQUEST
    status_code = 422
    default_message = "The generation request is not valid for the selected model."


def check_against_capabilities(request: ImageGenerateRequest, caps: ImageCapabilities) -> None:
    for name, value in (("width", request.width), ("height", request.height)):
        if value % caps.size_multiple:
            raise InvalidGenerationRequestError(f"{name} must be a multiple of {caps.size_multiple}.")
        if not caps.min_size <= value <= caps.max_size:
            raise InvalidGenerationRequestError(
                f"{name} must be between {caps.min_size} and {caps.max_size}."
            )
    if request.num_images > caps.max_images_per_request:
        raise InvalidGenerationRequestError(f"At most {caps.max_images_per_request} images per request.")
    if len(request.reference_asset_ids) > caps.max_reference_images:
        if caps.max_reference_images == 0:
            raise InvalidGenerationRequestError("This model does not accept reference images.")
        raise InvalidGenerationRequestError(f"At most {caps.max_reference_images} reference images.")
    if request.guidance_scale is not None and not caps.guidance:
        raise InvalidGenerationRequestError(
            "This model does not use a guidance scale (distilled checkpoint)."
        )


class _RefersToAssets(Protocol):
    @property
    def project_id(self) -> str | None: ...
    @property
    def character_id(self) -> str | None: ...
    @property
    def reference_asset_ids(self) -> list[str]: ...


def resolve_references(session: Session, storage: StorageService, request: _RefersToAssets) -> list[Path]:
    """Check project/character/consent and return reference image paths."""
    if request.project_id and session.get(Project, request.project_id) is None:
        raise NotFoundError("Project not found.")
    if request.character_id:
        character = session.get(Character, request.character_id)
        if character is None:
            raise NotFoundError("Character not found.")
        if character.is_real_person:
            require_active_consent(session, character.consent_id, ConsentSubject.FACE)
    paths = []
    for asset_id in request.reference_asset_ids:
        asset = get_asset(session, asset_id)
        if asset.kind is not AssetKind.IMAGE:
            raise UnsupportedFormatError("Reference assets must be images.")
        paths.append(storage.resolve(asset.path))
    return paths


def image_path(session: Session, storage: StorageService, asset_id: str, label: str) -> Path:
    asset = get_asset(session, asset_id)
    if asset.kind is not AssetKind.IMAGE:
        raise UnsupportedFormatError(f"The {label} must be an image.")
    return storage.resolve(asset.path)


def edit_output_size(
    request: ImageEditRequest, source_size: tuple[int, int], multiple: int
) -> tuple[int, int]:
    """Final size after snapping the source to `multiple` and adding outpaint padding."""
    width = source_size[0] - source_size[0] % multiple
    height = source_size[1] - source_size[1] % multiple
    if request.padding is not None:
        width += request.padding.left + request.padding.right
        height += request.padding.top + request.padding.bottom
    return width, height


def check_edit_against_capabilities(
    request: ImageEditRequest, caps: ImageCapabilities, source_size: tuple[int, int]
) -> None:
    if request.mode == "edit":
        if not caps.image_edit or caps.max_reference_images < 1:
            raise InvalidGenerationRequestError("This model cannot edit images from an instruction.")
        if 1 + len(request.reference_asset_ids) > caps.max_reference_images:
            raise InvalidGenerationRequestError(
                f"At most {caps.max_reference_images - 1} extra reference images (the source counts as one)."
            )
    else:
        if not caps.inpainting:
            raise InvalidGenerationRequestError("This model does not support inpainting/outpainting.")
        if len(request.reference_asset_ids) > caps.max_reference_images:
            raise InvalidGenerationRequestError(f"At most {caps.max_reference_images} reference images.")
    if request.num_images > caps.max_images_per_request:
        raise InvalidGenerationRequestError(f"At most {caps.max_images_per_request} images per request.")
    if request.guidance_scale is not None and not caps.guidance:
        raise InvalidGenerationRequestError(
            "This model does not use a guidance scale (distilled checkpoint)."
        )
    width, height = edit_output_size(request, source_size, caps.size_multiple)
    for name, value in (("width", width), ("height", height)):
        if not caps.min_size <= value <= caps.max_size:
            raise InvalidGenerationRequestError(
                f"Result {name} {value}px is outside {caps.min_size}-{caps.max_size}px for this model."
            )
