"""`image.edit`: instruction edit, masked inpaint or outpaint of an existing image.

For inpaint/outpaint the model output is composited back so that every pixel outside the mask is the
original pixel (the VAE round-trip would otherwise shift colors on logos, labels and faces).
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from PIL import Image

from app.models.enums import JobStatus
from app.providers.base import (
    ImageCapabilities,
    ImageGenerationProvider,
    ImageRequest,
    InpaintRequest,
    Maturity,
    ProviderKind,
)
from app.schemas.generation import MAX_SEED, ImageEditRequest
from app.services.assets import get_asset
from app.services.generation_store import ImageGenerationRecord, save_image_generation
from app.services.image_edit import feather, load_mask, outpaint_canvas, restore_unmasked, snap_to_multiple
from app.services.image_generation import check_edit_against_capabilities, image_path, resolve_references
from app.services.storage import StorageService
from app.workers.context import JobContext

logger = logging.getLogger(__name__)

JOB_TYPE = "image.edit"


def run_image_edit(ctx: JobContext) -> dict[str, Any]:
    request = ImageEditRequest.model_validate(ctx.payload)
    assert ctx.settings is not None
    storage = StorageService(ctx.settings.data_dir)

    caps = ctx.models.registry.get(ProviderKind.IMAGE, request.model_key).capabilities()
    assert isinstance(caps, ImageCapabilities)
    with ctx.session() as session:
        source_asset = get_asset(session, request.source_asset_id)
        check_edit_against_capabilities(request, caps, (source_asset.width or 0, source_asset.height or 0))
        references = resolve_references(session, storage, request)
        source_path = image_path(session, storage, request.source_asset_id, "source")
        mask_path = (
            image_path(session, storage, request.mask_asset_id, "mask") if request.mask_asset_id else None
        )

    ctx.report(2, stage="Preparing image")
    with Image.open(source_path) as img:
        source = snap_to_multiple(img.convert("RGB"), caps.size_multiple)
    work = source
    mask = None
    if request.mode == "inpaint":
        assert mask_path is not None
        mask = load_mask(mask_path, source.size)
    elif request.mode == "outpaint":
        assert request.padding is not None
        pad = request.padding
        canvas = outpaint_canvas(source, pad.left, pad.top, pad.right, pad.bottom)
        work, mask = canvas.canvas, canvas.mask

    work_path = ctx.temp_dir / "work.png"
    work.save(work_path)
    if mask is not None:
        mask.save(ctx.temp_dir / "mask.png")

    ctx.report(4, status=JobStatus.LOADING_MODEL, stage="Loading image model")
    started = time.monotonic()
    seed = request.seed if request.seed is not None else secrets.randbelow(MAX_SEED - 16)
    with ctx.models.use(ProviderKind.IMAGE, ImageGenerationProvider, request.model_key) as provider:
        caps = provider.capabilities()  # re-check after load (is_distilled comes from the pipeline)
        check_edit_against_capabilities(request, caps, source.size)
        steps = request.steps or caps.default_steps
        ctx.report(10, status=JobStatus.GENERATING_IMAGE, stage=f"{request.mode.capitalize()}ing image")
        gen_ctx = ctx.generation_context(10, 88)
        if request.mode == "edit":
            images = provider.generate(
                ImageRequest(
                    prompt=request.prompt, width=work.width, height=work.height, steps=steps, seed=seed,
                    num_images=request.num_images, guidance_scale=request.guidance_scale,
                    reference_images=[work_path, *references],  # the source is the first reference
                ),
                gen_ctx,
            )  # fmt: skip
        else:
            images = provider.inpaint(
                InpaintRequest(
                    prompt=request.prompt, width=work.width, height=work.height, steps=steps, seed=seed,
                    num_images=request.num_images, guidance_scale=request.guidance_scale,
                    reference_images=references, image=work_path, mask=ctx.temp_dir / "mask.png",
                    strength=request.effective_strength,
                ),
                gen_ctx,
            )  # fmt: skip
        model_key, provider_name = provider.key, provider.spec.provider
        model_source = provider.spec.local_path or provider.spec.repo_id
        placeholder = type(provider).maturity is Maturity.DEV_ONLY
    duration_ms = int((time.monotonic() - started) * 1000)

    if mask is not None:
        ctx.report(90, stage="Restoring untouched pixels")
        blend = feather(mask, request.feather)
        images = [restore_unmasked(image, work, blend) for image in images]

    ctx.report(93, stage="Saving images")
    seeds = [seed + i for i in range(len(images))]
    generation_id, asset_ids = save_image_generation(
        ctx.session,
        storage,
        images,
        ImageGenerationRecord(
            kind="image_edit",
            job_id=ctx.job_id,
            provider=provider_name,
            model_key=model_key,
            model_source=model_source,
            placeholder=placeholder,
            seeds=seeds,
            params={
                "mode": request.mode,
                "prompt": request.prompt,
                "width": images[0].width if images else work.width,
                "height": images[0].height if images else work.height,
                "steps": steps,
                "strength": None if request.mode == "edit" else request.effective_strength,
                "padding": request.padding.model_dump() if request.padding else None,
                "feather": request.feather,
                "guidance_scale": request.guidance_scale,
                "num_images": request.num_images,
            },
            input_asset_ids=[
                a for a in (request.source_asset_id, request.mask_asset_id, *request.reference_asset_ids) if a
            ],
            duration_ms=duration_ms,
            device=ctx.models.device.to_dict(),
            watermark=bool(request.watermark),
            project_id=request.project_id,
            character_id=request.character_id,
            extra_disclosure={
                "ai_edited": True,
                "edit_mode": request.mode,
                "edited_asset_id": request.source_asset_id,
            },
        ),
    )
    logger.info("image_edited", extra={"generation_id": generation_id, "mode": request.mode})
    return {"generation_id": generation_id, "asset_ids": asset_ids, "seeds": seeds}
