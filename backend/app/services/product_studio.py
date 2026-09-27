"""Validation shared by the Product Studio API and its worker jobs."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.enums import AssetKind, AssetRole
from app.models.links import ProductAsset
from app.models.product import Product
from app.providers.base import ImageCapabilities
from app.schemas.asset import AssetLinkCreate
from app.schemas.product_studio import PlacementIn, ProductSceneRequest
from app.services import products
from app.services.asset_links import attach_to_product
from app.services.assets import get_asset
from app.services.image_generation import InvalidGenerationRequestError
from app.services.storage import StorageService


def linked_image(
    session: Session,
    storage: StorageService,
    product: Product,
    asset_id: str,
    roles: set[AssetRole],
    label: str,
) -> Path:
    """Path of an image asset that belongs to `product` under one of `roles`."""
    if not any(link.asset_id == asset_id and link.role in roles for link in product.assets):
        raise InvalidGenerationRequestError(f"The {label} does not belong to this product.")
    asset = get_asset(session, asset_id)
    if asset.kind is not AssetKind.IMAGE:
        raise InvalidGenerationRequestError(f"The {label} must be an image.")
    return storage.resolve(asset.path)


def ensure_product_photo(session: Session, product: Product, asset_id: str) -> None:
    """Attach an uploaded photo to the product (role product_photo) unless it is already linked."""
    if any(link.asset_id == asset_id for link in product.assets):
        return
    attach_to_product(session, product, AssetLinkCreate(asset_id=asset_id, role=AssetRole.PRODUCT_PHOTO))


def next_position(product: Product, role: AssetRole) -> int:
    return 1 + max((link.position for link in product.assets if link.role is role), default=-1)


def link_asset(session: Session, product_id: str, asset_id: str, role: AssetRole) -> None:
    product = products.get_product(session, product_id)
    session.add(
        ProductAsset(
            product_id=product_id, asset_id=asset_id, role=role, position=next_position(product, role)
        )
    )


def placed_size(cutout: tuple[int, int], canvas: tuple[int, int], placement: PlacementIn) -> tuple[int, int]:
    """Size of the product on the canvas (mirrors compositing.place) — raises if it does not fit."""
    if placement.native_scale:
        size = cutout
    else:
        target_h = max(1, round(placement.height_ratio * canvas[1]))
        size = (max(1, round(cutout[0] * target_h / cutout[1])), target_h)
    if size[0] > canvas[0] or size[1] > canvas[1]:
        raise InvalidGenerationRequestError(
            f"The product ({size[0]}x{size[1]}px) does not fit the {canvas[0]}x{canvas[1]}px image; "
            "lower its size or use a larger format."
        )
    return size


def check_scene_capabilities(request: ProductSceneRequest, caps: ImageCapabilities) -> None:
    if request.background_asset_id is None and not caps.text_to_image:
        raise InvalidGenerationRequestError("This model cannot generate backgrounds.")
    if request.harmonize.enabled and not caps.inpainting:
        raise InvalidGenerationRequestError("Edge harmonisation needs a model with inpainting.")
    if len(request.reference_asset_ids) > caps.max_reference_images:
        raise InvalidGenerationRequestError(f"At most {caps.max_reference_images} reference images.")
    if request.num_images > caps.max_images_per_request:
        raise InvalidGenerationRequestError(f"At most {caps.max_images_per_request} images per request.")
    if request.guidance_scale is not None and not caps.guidance:
        raise InvalidGenerationRequestError(
            "This model does not use a guidance scale (distilled checkpoint)."
        )
    for name, value in (("width", request.width), ("height", request.height)):
        if not caps.min_size <= value <= caps.max_size or value % caps.size_multiple:
            raise InvalidGenerationRequestError(
                f"{name} {value}px must be {caps.min_size}-{caps.max_size}px "
                f"and a multiple of {caps.size_multiple}."
            )
