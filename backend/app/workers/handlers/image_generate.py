"""`image.generate`: prompt (+ optional reference images) → images stored as AI-generated assets."""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from app.core.ids import IdPrefix, new_id
from app.db.base import utcnow
from app.models.enums import JobStatus
from app.models.generation import Generation
from app.providers.base import (
    ImageCapabilities,
    ImageGenerationProvider,
    ImageRequest,
    Maturity,
    ProviderKind,
)
from app.schemas.generation import MAX_SEED, ImageGenerateRequest
from app.services.generated_media import delete_media_files, store_generated_image
from app.services.image_generation import check_against_capabilities, resolve_references
from app.services.storage import StorageService
from app.workers.context import JobContext

logger = logging.getLogger(__name__)

JOB_TYPE = "image.generate"


def run_image_generate(ctx: JobContext) -> dict[str, Any]:
    request = ImageGenerateRequest.model_validate(ctx.payload)
    assert ctx.settings is not None
    storage = StorageService(ctx.settings.data_dir)

    # Validate before loading weights: a bad request must not cost a multi-GB model load.
    caps = ctx.models.registry.get(ProviderKind.IMAGE, request.model_key).capabilities()
    assert isinstance(caps, ImageCapabilities)
    check_against_capabilities(request, caps)
    with ctx.session() as session:
        references = resolve_references(session, storage, request)

    ctx.report(3, status=JobStatus.LOADING_MODEL, stage="Loading image model")
    started = time.monotonic()
    with ctx.models.use(ProviderKind.IMAGE, ImageGenerationProvider, request.model_key) as provider:
        caps = provider.capabilities()  # may change after load (e.g. is_distilled from config)
        check_against_capabilities(request, caps)
        steps = request.steps or caps.default_steps
        seed = request.seed if request.seed is not None else secrets.randbelow(MAX_SEED - 16)
        count = request.num_images
        ctx.report(
            10, status=JobStatus.GENERATING_IMAGE, stage=f"Generating {count} image{'s' * (count > 1)}"
        )
        images = provider.generate(
            ImageRequest(
                prompt=request.prompt,
                width=request.width,
                height=request.height,
                steps=steps,
                seed=seed,
                num_images=count,
                guidance_scale=request.guidance_scale,
                reference_images=references,
            ),
            ctx.generation_context(10, 90),
        )
        model_key, provider_name = provider.key, provider.spec.provider
        model_source = provider.spec.local_path or provider.spec.repo_id
        placeholder = type(provider).maturity is Maturity.DEV_ONLY
    duration_ms = int((time.monotonic() - started) * 1000)

    ctx.report(92, stage="Saving images")
    seeds = [seed + i for i in range(len(images))]
    generation_id = new_id(IdPrefix.GENERATION)
    created_at = utcnow().isoformat()
    stored = []
    with ctx.session() as session:
        try:
            for image, image_seed in zip(images, seeds, strict=True):
                disclosure = {
                    "generated_with_ai": not placeholder,
                    "dev_placeholder": placeholder,
                    "model": model_key,
                    "provider": provider_name,
                    "seed": image_seed,
                    "created_at": created_at,
                    "generation_id": generation_id,
                    "project_id": request.project_id,
                    "character_id": request.character_id,
                    "source_asset_ids": request.reference_asset_ids,
                }
                stored.append(
                    store_generated_image(
                        session, storage, image, disclosure, watermark=bool(request.watermark)
                    )
                )
            session.add(
                Generation(
                    id=generation_id,
                    kind="image",
                    job_id=ctx.job_id,
                    project_id=request.project_id,
                    character_id=request.character_id,
                    provider=provider_name,
                    model_key=model_key,
                    model_source=model_source,
                    params={
                        "prompt": request.prompt,
                        "width": request.width,
                        "height": request.height,
                        "steps": steps,
                        "guidance_scale": request.guidance_scale,
                        "num_images": count,
                        "watermark": bool(request.watermark),
                    },
                    seeds=seeds,
                    input_asset_ids=request.reference_asset_ids,
                    output_asset_ids=[a.id for a in stored],
                    duration_ms=duration_ms,
                    device=ctx.models.device.to_dict(),
                )
            )
            session.commit()
        except BaseException:
            session.rollback()
            delete_media_files(storage, stored)
            raise

    logger.info(
        "image_generated", extra={"generation_id": generation_id, "count": len(stored), "ms": duration_ms}
    )
    return {"generation_id": generation_id, "asset_ids": [a.id for a in stored], "seeds": seeds}
