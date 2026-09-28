"""`video.generate`: image-to-video / text-to-video (Wan) or deterministic camera motion (no AI)."""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from PIL import Image, ImageOps

from app.models.enums import JobStatus
from app.providers.base import (
    Maturity,
    ProviderKind,
    VideoCapabilities,
    VideoGenerationProvider,
    VideoRequest,
)
from app.schemas.generation import MAX_SEED
from app.schemas.video import VideoGenerateRequest
from app.services.ffmpeg.binary import require_binary
from app.services.generation_store import ImageGenerationRecord, save_video_generation
from app.services.image_generation import image_path, resolve_references
from app.services.storage import StorageService
from app.services.video_generation import check_video_against_capabilities, frame_count
from app.workers.context import JobContext

logger = logging.getLogger(__name__)

JOB_TYPE = "video.generate"


def _prepare_frame(path: Any, size: tuple[int, int], out: Any) -> Any:
    """Cover-fit the conditioning image to the output size (centre crop, never stretched)."""
    with Image.open(path) as img:
        ImageOps.fit(ImageOps.exif_transpose(img).convert("RGB"), size, Image.Resampling.LANCZOS).save(out)
    return out


def run_video_generate(ctx: JobContext) -> dict[str, Any]:
    request = VideoGenerateRequest.model_validate(ctx.payload)
    assert ctx.settings is not None
    storage = StorageService(ctx.settings.data_dir)
    ffmpeg = require_binary("ffmpeg", ctx.settings.ffmpeg_path)

    caps = ctx.models.registry.get(ProviderKind.VIDEO, request.model_key).capabilities()
    assert isinstance(caps, VideoCapabilities)
    check_video_against_capabilities(request, caps)
    with ctx.session() as session:
        resolve_references(session, storage, request)  # project/character/consent checks
        first = (
            image_path(session, storage, request.image_asset_id, "start image")
            if request.image_asset_id
            else None
        )
        last = (
            image_path(session, storage, request.last_image_asset_id, "last image")
            if request.last_image_asset_id
            else None
        )

    size = (request.width, request.height)
    first_frame = _prepare_frame(first, size, ctx.temp_dir / "first.png") if first else None
    last_frame = _prepare_frame(last, size, ctx.temp_dir / "last.png") if last else None
    seed = request.seed if request.seed is not None else secrets.randbelow(MAX_SEED - 16)

    ctx.report(3, status=JobStatus.LOADING_MODEL, stage="Loading video model")
    started = time.monotonic()
    with ctx.models.use(ProviderKind.VIDEO, VideoGenerationProvider, request.model_key) as provider:
        caps = provider.capabilities()  # size multiple / frame step may be read from the loaded pipeline
        fps = check_video_against_capabilities(request, caps)
        frames = frame_count(request.duration_s, fps, caps)
        steps = request.steps or caps.default_steps
        ctx.report(8, status=JobStatus.GENERATING_VIDEO, stage="Generating video")
        output = provider.generate(
            VideoRequest(
                prompt=request.prompt, width=request.width, height=request.height, num_frames=frames, fps=fps,
                steps=steps, seed=seed, image=first_frame, last_image=last_frame,
                guidance_scale=request.guidance_scale, negative_prompt=request.negative_prompt,
                motion=request.motion, motion_strength=request.motion_strength,
            ),
            ctx.temp_dir / "clip.mp4",
            ctx.generation_context(8, 92),
        )  # fmt: skip
        model_key, provider_name = provider.key, provider.spec.provider
        model_source = provider.spec.local_path or provider.spec.repo_id
        placeholder = type(provider).maturity is Maturity.DEV_ONLY
    duration_ms = int((time.monotonic() - started) * 1000)

    ctx.report(94, status=JobStatus.ENCODING, stage="Saving video")
    uses_ai = caps.uses_ai
    generation_id, asset_id = save_video_generation(
        ctx.session,
        storage,
        output,
        ImageGenerationRecord(
            kind="video",
            job_id=ctx.job_id,
            provider=provider_name,
            model_key=model_key,
            model_source=model_source,
            placeholder=placeholder,
            seeds=[seed],
            params={
                "prompt": request.prompt,
                "width": request.width,
                "height": request.height,
                "fps": fps,
                "num_frames": frames,
                "duration_s": round(frames / fps, 3),
                "steps": steps if uses_ai else None,
                "guidance_scale": request.guidance_scale,
                "motion": request.motion,
                "motion_strength": request.motion_strength,
                "mode": "image_to_video" if first_frame else "text_to_video",
            },
            input_asset_ids=request.reference_asset_ids,
            duration_ms=duration_ms,
            device=ctx.models.device.to_dict(),
            watermark=False,
            ai_generated=uses_ai,
            project_id=request.project_id,
            character_id=request.character_id,
            extra_disclosure={
                "video_method": "ai_video" if uses_ai else "camera_motion",
                "disclosure_label": "ai_generated" if uses_ai else "no_ai",
                "camera_motion": request.motion,
            },
        ),
        ffmpeg=ffmpeg,
        ffprobe_path=ctx.settings.ffprobe_path,
        run=ctx.run_subprocess,
        temp_dir=ctx.temp_dir,
        shot_id=request.shot_id,
    )
    logger.info("video_generated", extra={"generation_id": generation_id, "model": model_key})
    return {
        "generation_id": generation_id,
        "asset_id": asset_id,
        "seed": seed,
        "num_frames": frames,
        "fps": fps,
    }
