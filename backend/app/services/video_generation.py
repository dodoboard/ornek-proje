"""Validation of video requests against a provider's capabilities (API and worker share it)."""

from __future__ import annotations

from app.providers.base import VideoCapabilities
from app.schemas.video import VideoGenerateRequest
from app.services.image_generation import InvalidGenerationRequestError


def frame_count(duration_s: float, fps: int, caps: VideoCapabilities) -> int:
    """Frames for the duration, snapped to `frame_step * k + 1` and capped by `max_frames`."""
    frames = max(2, round(duration_s * fps))
    step = max(1, caps.frame_step)
    if step > 1:
        k = max(1, round((frames - 1) / step))
        while k * step + 1 > caps.max_frames and k > 1:
            k -= 1
        return k * step + 1
    return min(frames, caps.max_frames)


def check_video_against_capabilities(request: VideoGenerateRequest, caps: VideoCapabilities) -> int:
    """Raise a user-facing error for anything the model cannot do; returns the fps to use."""
    if request.image_asset_id is None and not caps.text_to_video:
        raise InvalidGenerationRequestError("This model needs a start image (image-to-video only).")
    if request.last_image_asset_id and not caps.last_frame_conditioning:
        raise InvalidGenerationRequestError("This model does not support a last-frame image.")
    if caps.uses_ai and not request.prompt:
        raise InvalidGenerationRequestError("Describe the motion/scene in the prompt.")
    if request.negative_prompt and not caps.negative_prompt:
        raise InvalidGenerationRequestError("This model does not use a negative prompt.")
    if request.guidance_scale is not None and not caps.guidance:
        raise InvalidGenerationRequestError("This model does not use a guidance scale.")
    fps = request.fps or caps.fps[0]
    if fps not in caps.fps:
        raise InvalidGenerationRequestError(f"Supported frame rates: {', '.join(map(str, caps.fps))} fps.")
    for name, value in (("width", request.width), ("height", request.height)):
        if not caps.min_size <= value <= caps.max_size or value % caps.size_multiple:
            raise InvalidGenerationRequestError(
                f"{name} {value}px must be {caps.min_size}-{caps.max_size}px and a multiple of "
                f"{caps.size_multiple} for this model."
            )
    if round(request.duration_s * fps) > caps.max_frames + caps.frame_step:
        raise InvalidGenerationRequestError(
            f"At most {caps.max_frames} frames ({caps.max_frames / fps:.1f} s at {fps} fps) for this model."
        )
    return fps
