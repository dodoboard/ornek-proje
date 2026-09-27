"""Product Studio jobs.

`product.cutout`: segment a product photo → RGBA cutout with the photo's exact RGB (+ mask asset).
`product.scene`: background (generated or user photo) + the original product pixels composited on top,
optional contact shadow and AI edge harmonisation in a thin ring; a preservation check proves that the
protected product pixels are unchanged, otherwise the job fails.
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from PIL import Image, ImageOps

from app.core.errors import GenerationFailedError
from app.models.enums import AssetRole, JobStatus
from app.providers.base import (
    ImageCapabilities,
    ImageGenerationProvider,
    ImageRequest,
    InpaintRequest,
    Maturity,
    ProviderKind,
    SegmentationProvider,
)
from app.schemas.generation import MAX_SEED
from app.schemas.product_studio import ProductCutoutRequest, ProductSceneRequest
from app.services import products
from app.services.compositing import (
    PlacedProduct,
    Placement,
    composite,
    contact_shadow,
    edge_ring,
    make_cutout,
    place,
    preservation_report,
    protect,
    protected_mask,
)
from app.services.generated_media import apply_watermark, delete_media_files, store_derived_image
from app.services.generation_store import ImageGenerationRecord, save_image_generation
from app.services.image_edit import load_mask, restore_unmasked
from app.services.image_generation import image_path, resolve_references
from app.services.product_studio import check_scene_capabilities, link_asset, linked_image, placed_size
from app.services.prompts.product import ProductPromptBuilder
from app.services.storage import StorageService
from app.workers.context import JobContext

logger = logging.getLogger(__name__)

CUTOUT_JOB = "product.cutout"
SCENE_JOB = "product.scene"
PHOTO_ROLES = {AssetRole.PRODUCT_PHOTO, AssetRole.REFERENCE}


def _product_id(ctx: JobContext) -> str:
    product_id = ctx.payload.get("product_id")
    if not isinstance(product_id, str):
        raise GenerationFailedError("Job payload is missing product_id.")
    return product_id


# --------------------------------------------------------------------------- cutout


def run_product_cutout(ctx: JobContext) -> dict[str, Any]:
    product_id = _product_id(ctx)
    request = ProductCutoutRequest.model_validate({k: v for k, v in ctx.payload.items() if k != "product_id"})
    assert ctx.settings is not None
    storage = StorageService(ctx.settings.data_dir)

    with ctx.session() as session:
        product = products.get_product(session, product_id)
        photo_path = linked_image(session, storage, product, request.source_asset_id, PHOTO_ROLES, "photo")
        mask_path = (
            image_path(session, storage, request.mask_asset_id, "mask") if request.mask_asset_id else None
        )

    with Image.open(photo_path) as img:
        photo = ImageOps.exif_transpose(img).convert("RGB")

    model_key = "user_mask"
    if mask_path is not None:
        ctx.report(20, status=JobStatus.PROCESSING_PRODUCT, stage="Applying your mask")
        mask = load_mask(mask_path, photo.size)
    else:
        ctx.report(5, status=JobStatus.LOADING_MODEL, stage="Loading segmentation model")
        with ctx.models.use(ProviderKind.SEGMENTATION, SegmentationProvider, request.model_key) as provider:
            ctx.report(15, status=JobStatus.PROCESSING_PRODUCT, stage="Separating product from background")
            mask = provider.segment(photo, ctx.generation_context(15, 85))
            model_key = provider.key

    ctx.report(88, stage="Saving cutout")
    try:
        cutout = make_cutout(photo, mask)
    except ValueError as exc:
        raise GenerationFailedError(str(exc)) from exc

    meta = {
        "derived_from": request.source_asset_id,
        "product_id": product_id,
        "segmentation_model": model_key,
        "generated_with_ai": False,
        "note": "RGB pixels are the original photo; only the alpha channel comes from segmentation.",
    }
    stored = []
    with ctx.session() as session:
        try:
            cutout_asset = store_derived_image(
                session, storage, cutout, {**meta, "derived": "product_cutout"}
            )
            stored.append(cutout_asset)
            mask_asset = store_derived_image(session, storage, mask, {**meta, "derived": "product_mask"})
            stored.append(mask_asset)
            session.flush()
            link_asset(session, product_id, cutout_asset.id, AssetRole.CUTOUT)
            link_asset(session, product_id, mask_asset.id, AssetRole.MASK)
            session.commit()
        except BaseException:
            session.rollback()
            delete_media_files(storage, stored)
            raise
    logger.info("product_cutout", extra={"product_id": product_id, "model": model_key})
    return {
        "cutout_asset_id": stored[0].id,
        "mask_asset_id": stored[1].id,
        "width": cutout.width,
        "height": cutout.height,
        "segmentation_model": model_key,
    }


# --------------------------------------------------------------------------- scene


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale and centre-crop a background photo to exactly `size`."""
    return ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS)


def _finish(
    base: Image.Image, placed: PlacedProduct, harmonised: Image.Image | None, ring: Image.Image | None,
    core: Image.Image, watermark: bool,
) -> tuple[Image.Image, dict[str, Any]]:  # fmt: skip
    """Restore everything outside the ring, re-apply protected product pixels, label, then verify."""
    final = base
    if harmonised is not None and ring is not None:
        final = protect(restore_unmasked(harmonised, base, ring), placed.layer, core)
    if watermark:
        final = apply_watermark(final, avoid=placed.box)
    report = preservation_report(final, placed, core)
    report["watermark"] = watermark
    if not report["exact"]:
        raise GenerationFailedError(
            f"Product preservation check failed ({report['mismatched_pixels']} protected pixels changed)."
        )
    return final, report


def run_product_scene(ctx: JobContext) -> dict[str, Any]:
    product_id = _product_id(ctx)
    request = ProductSceneRequest.model_validate({k: v for k, v in ctx.payload.items() if k != "product_id"})
    assert ctx.settings is not None
    storage = StorageService(ctx.settings.data_dir)
    canvas = (request.width, request.height)

    with ctx.session() as session:
        product = products.get_product(session, product_id)
        cutout_path = linked_image(
            session, storage, product, request.cutout_asset_id, {AssetRole.CUTOUT}, "cutout"
        )
        background_path = (
            image_path(session, storage, request.background_asset_id, "background")
            if request.background_asset_id
            else None
        )
        references = resolve_references(session, storage, request)

    with Image.open(cutout_path) as img:
        cutout = img.convert("RGBA")
    placed_size(cutout.size, canvas, request.placement)
    p = request.placement
    placed = place(cutout, canvas, Placement(p.x, p.y, p.height_ratio, p.native_scale))
    ring_px = request.harmonize.ring_px if request.harmonize.enabled else 0
    core = protected_mask(placed, ring_px)
    ring = edge_ring(placed, ring_px) if request.harmonize.enabled else None
    prompts = ProductPromptBuilder(request.scene, p.x, p.y)
    watermark = bool(request.watermark)
    seed = request.seed if request.seed is not None else secrets.randbelow(MAX_SEED - 16)
    seeds = [seed + i for i in range(request.num_images)]
    started = time.monotonic()

    model_info: dict[str, Any] = {
        "model_key": "compositor", "provider": "compositor", "model_source": None, "placeholder": False,
    }  # fmt: skip
    steps: int | None = None
    if background_path is not None:
        with Image.open(background_path) as img:
            backgrounds = [cover(img, canvas)] * request.num_images
    else:
        backgrounds = []

    bases: list[Image.Image] = []
    harmonised: list[Image.Image | None] = [None] * request.num_images
    if request.uses_model:
        ctx.report(3, status=JobStatus.LOADING_MODEL, stage="Loading image model")
        with ctx.models.use(ProviderKind.IMAGE, ImageGenerationProvider, request.model_key) as provider:
            caps = provider.capabilities()
            assert isinstance(caps, ImageCapabilities)
            check_scene_capabilities(request, caps)
            steps = request.steps or caps.default_steps
            if not backgrounds:
                ctx.report(8, status=JobStatus.GENERATING_IMAGE, stage="Generating background")
                end = 60 if request.harmonize.enabled else 85
                backgrounds = provider.generate(
                    ImageRequest(
                        prompt=prompts.background(), width=canvas[0], height=canvas[1], steps=steps,
                        seed=seed, num_images=request.num_images, guidance_scale=request.guidance_scale,
                        reference_images=references,
                    ),
                    ctx.generation_context(8, end),
                )  # fmt: skip
            ctx.report(62, status=JobStatus.PROCESSING_PRODUCT, stage="Placing the original product")
            bases = [_compose(bg, placed, request) for bg in backgrounds]
            if request.harmonize.enabled and ring is not None:
                ring.save(ctx.temp_dir / "ring.png")
                span = 28 / len(bases)
                for i, base in enumerate(bases):
                    ctx.report(64 + i * span, stage=f"Blending product edges ({i + 1}/{len(bases)})")
                    base.save(ctx.temp_dir / f"base_{i}.png")
                    harmonised[i] = provider.inpaint(
                        InpaintRequest(
                            prompt=prompts.harmonize(), width=canvas[0], height=canvas[1], steps=steps,
                            seed=seeds[i], num_images=1, guidance_scale=request.guidance_scale,
                            reference_images=references, image=ctx.temp_dir / f"base_{i}.png",
                            mask=ctx.temp_dir / "ring.png", strength=request.harmonize.strength,
                        ),
                        ctx.generation_context(64 + i * span, 64 + (i + 1) * span),
                    )[0]  # fmt: skip
            model_info = {
                "model_key": provider.key,
                "provider": provider.spec.provider,
                "model_source": provider.spec.local_path or provider.spec.repo_id,
                "placeholder": type(provider).maturity is Maturity.DEV_ONLY,
            }
    else:
        ctx.report(40, status=JobStatus.PROCESSING_PRODUCT, stage="Placing the original product")
        bases = [_compose(bg, placed, request) for bg in backgrounds]
    duration_ms = int((time.monotonic() - started) * 1000)

    ctx.report(93, stage="Verifying product pixels")
    finals, reports = [], []
    for base, extra in zip(bases, harmonised, strict=True):
        final, report = _finish(base, placed, extra, ring, core, watermark)
        finals.append(final)
        reports.append(report)

    ctx.report(96, stage="Saving images")
    background_source = "user_photo" if request.background_asset_id else "ai_generated"
    generation_id, asset_ids = save_image_generation(
        ctx.session,
        storage,
        finals,
        ImageGenerationRecord(
            kind="product_scene",
            job_id=ctx.job_id,
            provider=model_info["provider"],
            model_key=model_info["model_key"],
            model_source=model_info["model_source"],
            placeholder=model_info["placeholder"],
            seeds=seeds,
            params={
                "scene": request.scene,
                "prompt": prompts.background() if request.background_asset_id is None else None,
                "width": canvas[0],
                "height": canvas[1],
                "steps": steps,
                "placement": p.model_dump(),
                "shadow": request.shadow,
                "shadow_opacity": request.shadow_opacity,
                "harmonize": request.harmonize.model_dump(),
                "background": background_source,
                "num_images": request.num_images,
                "preservation": reports,
                "watermark": watermark,
            },
            input_asset_ids=[
                a
                for a in (request.cutout_asset_id, request.background_asset_id, *request.reference_asset_ids)
                if a
            ],
            duration_ms=duration_ms,
            device=ctx.models.device.to_dict(),
            watermark=False,  # already applied above, placed away from the product and verified
            ai_generated=request.uses_model,
            project_id=request.project_id,
            character_id=request.character_id,
            product_id=product_id,
            extra_disclosure={
                "product_pixels": "original_photo",
                "product_scale": round(placed.scale, 4),
                "product_box": list(placed.box),
                "background": background_source,
                "edge_harmonized": request.harmonize.enabled,
                "cutout_asset_id": request.cutout_asset_id,
                "watermark": watermark,
            },
        ),
    )
    logger.info("product_scene", extra={"generation_id": generation_id, "product_id": product_id})
    return {"generation_id": generation_id, "asset_ids": asset_ids, "seeds": seeds, "preservation": reports}


def _compose(background: Image.Image, placed: PlacedProduct, request: ProductSceneRequest) -> Image.Image:
    bg = background.convert("RGB")
    if request.shadow and request.shadow_opacity > 0:
        bg = contact_shadow(bg, placed.box, request.shadow_opacity)
    return composite(bg, placed)
