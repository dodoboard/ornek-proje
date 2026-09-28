"""Deterministic camera moves over a still image (Ken Burns) — no AI, no new pixels are invented.

Frames are rendered with Pillow using sub-pixel affine crops (smooth, no zoompan jitter) and encoded
with FFmpeg. Used for product close-ups (the original product pixels move, nothing is regenerated),
real-estate photos and text cards.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import PerformanceProfile
from app.core.errors import FileInvalidError, GenerationFailedError
from app.providers.base import (
    Availability,
    GenerationContext,
    ProviderStatus,
    VideoCapabilities,
    VideoGenerationProvider,
    VideoRequest,
)
from app.providers.device import DeviceInfo
from app.services.ffmpeg.binary import require_binary, resolve_binary
from app.services.ffmpeg.encode import encode_png_sequence, write_frames

MOTIONS = (
    "static",
    "slow_push_in",
    "pull_out",
    "pan_left",
    "pan_right",
    "tilt_up",
    "tilt_down",
    "orbit",
    "handheld",
)
ZOOM = 0.18  # push-in/pull-out: 18 % closer at full strength
TRAVEL = 0.12  # pans/tilts: 12 % of the frame at full strength


def _ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)  # smooth start and stop


def crop_boxes(
    size: tuple[int, int], target: tuple[int, int], motion: str, frames: int, strength: float = 1.0
) -> Iterator[tuple[float, float, float, float]]:
    """Source crop box (left, top, right, bottom; float) for every output frame."""
    width, height = size
    aspect = target[0] / target[1]
    base_w = min(width, height * aspect)
    base_h = base_w / aspect
    zoom_amount = ZOOM * strength
    travel = TRAVEL * strength
    for i in range(frames):
        t = _ease(i / max(1, frames - 1))
        scale = 1.0
        dx = dy = 0.0
        if motion == "slow_push_in":
            scale = 1 - zoom_amount * t
        elif motion == "pull_out":
            scale = 1 - zoom_amount * (1 - t)
        elif motion in ("pan_left", "pan_right", "tilt_up", "tilt_down", "orbit", "handheld"):
            scale = 1 - travel  # leave room to move inside the image
            direction = {"pan_left": (-1, 0), "pan_right": (1, 0), "tilt_up": (0, -1), "tilt_down": (0, 1)}
            if motion in direction:
                ddx, ddy = direction[motion]
                dx, dy = ddx * (t - 0.5), ddy * (t - 0.5)
            elif motion == "orbit":
                angle = 2 * math.pi * i / max(1, frames)
                dx, dy = 0.4 * math.cos(angle), 0.25 * math.sin(angle)
            else:  # handheld: small smooth wobble
                dx = 0.15 * math.sin(i * 0.21) + 0.08 * math.sin(i * 0.53)
                dy = 0.12 * math.sin(i * 0.17 + 1.3) + 0.06 * math.sin(i * 0.61)
        crop_w, crop_h = base_w * scale, base_h * scale
        cx = width / 2 + dx * (base_w - crop_w)  # dx in [-0.5, 0.5] spans the free room
        cy = height / 2 + dy * (base_h - crop_h)
        left = min(max(cx - crop_w / 2, 0.0), width - crop_w)
        top = min(max(cy - crop_h / 2, 0.0), height - crop_h)
        yield left, top, left + crop_w, top + crop_h


def render_frames(
    image: Image.Image, target: tuple[int, int], motion: str, frames: int, strength: float = 1.0
) -> Iterator[Image.Image]:
    source = image.convert("RGB")
    for box in crop_boxes(source.size, target, motion, frames, strength):
        yield source.resize(target, Image.Resampling.BICUBIC, box=box)


class FfmpegMotionProvider(VideoGenerationProvider):
    heavy = False

    def availability(self) -> Availability:
        if resolve_binary("ffmpeg", self.settings.ffmpeg_path) is None:
            return Availability(ProviderStatus.NOT_INSTALLED, "FFmpeg is required for camera-motion clips.")
        return Availability(ProviderStatus.AVAILABLE, "No AI: camera moves over your image.")

    def capabilities(self) -> VideoCapabilities:
        return VideoCapabilities(
            image_to_video=True, text_to_video=False, last_frame_conditioning=False, negative_prompt=False,
            guidance=False, camera_control=True, uses_ai=False, fps=(24, 25, 30), max_frames=30 * 20,
            frame_step=1, size_multiple=2, min_size=128, max_size=3840, default_steps=1,
        )  # fmt: skip

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate(self, request: VideoRequest, output: Path, ctx: GenerationContext) -> Path:
        if request.image is None:
            raise FileInvalidError("Camera-motion clips need an input image.")
        if request.motion not in MOTIONS:
            raise GenerationFailedError(f"Unknown camera motion '{request.motion}'.")
        ffmpeg = require_binary("ffmpeg", self.settings.ffmpeg_path)
        with Image.open(request.image) as img:
            source = ImageOps.exif_transpose(img).convert("RGB")
        target = (request.width, request.height)
        frames_dir = ctx.temp_dir / "motion_frames"
        total = request.num_frames
        write_frames(
            render_frames(source, target, request.motion, total, request.motion_strength),
            frames_dir,
            on_frame=lambda n: ctx.progress(0.7 * n / total),
        )
        return encode_png_sequence(
            ffmpeg, frames_dir, request.fps, output, ctx.run_subprocess,
            lambda f: ctx.progress(0.7 + 0.3 * f), total,
        )  # fmt: skip
