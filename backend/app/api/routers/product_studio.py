"""Product Studio: product cutouts and scenes that keep the product's original pixels."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import SessionDep, SettingsDep, StorageDep
from app.models.enums import AssetRole
from app.providers.base import ImageCapabilities, ProviderKind
from app.schemas.job import JobRead
from app.schemas.product_studio import ProductCutoutRequest, ProductSceneRequest
from app.services import products
from app.services.assets import get_asset
from app.services.image_generation import image_path, resolve_references
from app.services.model_selection import require_available
from app.services.preferences import build_registry, load_preferences
from app.services.product_studio import (
    check_scene_capabilities,
    ensure_product_photo,
    linked_image,
    placed_size,
)
from app.workers.handlers.product import CUTOUT_JOB, PHOTO_ROLES, SCENE_JOB
from app.workers.queue import JobQueue

router = APIRouter(prefix="/products/{product_id}", tags=["product-studio"])


@router.post("/cutout", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def create_cutout(
    product_id: str,
    body: ProductCutoutRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> JobRead:
    """Separate the product from its photo. The photo is attached to the product if it is not yet."""
    product = products.get_product(session, product_id)
    image_path(session, storage, body.source_asset_id, "photo")
    ensure_product_photo(session, product, body.source_asset_id)
    linked_image(session, storage, product, body.source_asset_id, PHOTO_ROLES, "photo")
    payload = body.model_dump(mode="json")
    if body.mask_asset_id:
        image_path(session, storage, body.mask_asset_id, "mask")
    else:
        registry = build_registry(settings, load_preferences(session, settings))
        payload["model_key"] = require_available(registry, ProviderKind.SEGMENTATION, body.model_key).key
    job = JobQueue(request.app.state.session_factory).enqueue(
        CUTOUT_JOB, {**payload, "product_id": product_id}
    )
    return JobRead.model_validate(job)


@router.post("/scene", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def create_scene(
    product_id: str,
    body: ProductSceneRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> JobRead:
    """Background + original product pixels (+ optional shadow and AI edge blending), verified."""
    product = products.get_product(session, product_id)
    linked_image(session, storage, product, body.cutout_asset_id, {AssetRole.CUTOUT}, "cutout")
    cutout = get_asset(session, body.cutout_asset_id)
    placed_size((cutout.width or 1, cutout.height or 1), (body.width, body.height), body.placement)
    if body.background_asset_id:
        image_path(session, storage, body.background_asset_id, "background")
    resolve_references(session, storage, body)

    prefs = load_preferences(session, settings)
    update: dict[str, object] = {
        "watermark": prefs.ai_watermark if body.watermark is None else body.watermark
    }
    if body.uses_model:
        registry = build_registry(settings, prefs)
        info = require_available(registry, ProviderKind.IMAGE, body.model_key)
        check_scene_capabilities(body, ImageCapabilities.model_validate(info.capabilities))
        update["model_key"] = info.key
    payload = body.model_copy(update=update).model_dump(mode="json")
    job = JobQueue(request.app.state.session_factory).enqueue(
        SCENE_JOB, {**payload, "product_id": product_id}, project_id=body.project_id
    )
    return JobRead.model_validate(job)
