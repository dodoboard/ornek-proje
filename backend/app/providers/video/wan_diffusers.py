"""Wan 2.x video provider via Diffusers (`WanPipeline` text-to-video, `WanImageToVideoPipeline`).

API facts used here were read from diffusers v0.40.0 source (pipelines/wan):
- `WanImageToVideoPipeline.__call__(image, prompt, negative_prompt, height, width, num_frames,
  num_inference_steps, guidance_scale, generator, last_image, output_type, callback_on_step_end, ...)`;
  `WanPipeline.__call__` is the same without `image`/`last_image`.
- `num_frames - 1` must be divisible by `vae_scale_factor_temporal` (4); height/width must be multiples
  of `vae_scale_factor_spatial * transformer.config.patch_size` (Wan2.2 TI2V-5B: 16 * 2 = 32).
- Wan2.2 TI2V-5B ("expand_timesteps") does T2V and I2V with the same components, so the other
  pipeline is built with `from_pipe` (optional config such as `expand_timesteps` is carried over).
- `output_type="pil"` → `result.frames[0]` is a list of PIL frames; we encode them with FFmpeg.
Wan2.2 README: TI2V-5B runs 720p (1280x704 / 704x1280) at 24 fps.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from app.core.config import PerformanceProfile
from app.core.errors import FileInvalidError, ProviderUnavailableError
from app.providers.base import (
    GenerationContext,
    VideoCapabilities,
    VideoGenerationProvider,
    VideoRequest,
)
from app.providers.catalog import resolve_local_path
from app.providers.device import DeviceInfo
from app.providers.memory import apply_pipeline_optimizations
from app.services.ffmpeg.binary import require_binary
from app.services.ffmpeg.encode import encode_png_sequence, write_frames

logger = logging.getLogger(__name__)

T2V_CLASS = "WanPipeline"
I2V_CLASS = "WanImageToVideoPipeline"
MIN_DIFFUSERS = "0.40.0"
DEFAULT_NEGATIVE = (
    "blurry, low quality, jpeg artifacts, distorted, deformed hands, extra fingers, watermark, subtitles, "
    "static frame, flicker"
)
MOTION_TEXT = {
    "static": "static camera",
    "slow_push_in": "slow camera push-in",
    "pull_out": "camera slowly pulls out",
    "pan_left": "camera pans left",
    "pan_right": "camera pans right",
    "tilt_up": "camera tilts up",
    "tilt_down": "camera tilts down",
    "orbit": "camera slowly orbits the subject",
    "handheld": "subtle handheld camera movement",
}


def _open_rgb(path: Path, size: tuple[int, int]) -> Image.Image:
    try:
        with Image.open(path) as img:
            return ImageOps.fit(ImageOps.exif_transpose(img).convert("RGB"), size, Image.Resampling.LANCZOS)
    except OSError as exc:
        raise FileInvalidError("An input image could not be read.") from exc


class WanDiffusersProvider(VideoGenerationProvider):
    required_packages = ("torch", "diffusers", "transformers", "accelerate", "ftfy")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pipes: dict[str, Any] = {}
        self._size_multiple: int | None = None
        self._frame_step: int | None = None

    def capabilities(self) -> VideoCapabilities:
        return VideoCapabilities(
            image_to_video=True,
            text_to_video=bool(self.spec.option("text_to_video", True)),
            last_frame_conditioning=bool(self.spec.option("last_frame_conditioning", False)),
            negative_prompt=True,
            guidance=True,
            default_guidance=float(self.spec.option("default_guidance", 5.0)),
            fps=tuple(self.spec.option("fps", (24,))),
            max_frames=int(self.spec.option("max_frames", 121)),
            frame_step=self._frame_step or int(self.spec.option("frame_step", 4)),
            size_multiple=self._size_multiple or int(self.spec.option("size_multiple", 32)),
            min_size=256,
            max_size=int(self.spec.option("max_size", 1280)),
            default_steps=int(self.spec.option("default_steps", 50)),
        )

    def model_source(self) -> str:
        local = resolve_local_path(self.spec.local_path, self.settings)
        if local is not None:
            return str(local)
        if not self.spec.repo_id:
            raise ProviderUnavailableError(f"'{self.key}' has neither a repo_id nor a local_path.")
        return self.spec.repo_id

    # ------------------------------------------------------------------ lifecycle

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        import diffusers
        import torch

        for name in (T2V_CLASS, I2V_CLASS):
            if getattr(diffusers, name, None) is None:
                raise ProviderUnavailableError(
                    f"diffusers has no {name}; install diffusers>={MIN_DIFFUSERS}."
                )
        # The repo's model_index.json decides which Wan pipeline class is stored there.
        pipe = diffusers.DiffusionPipeline.from_pretrained(
            self.model_source(),
            torch_dtype=getattr(torch, device.dtype),
            revision=self.spec.revision,
            local_files_only=self.settings.offline_mode,
        )
        class_name = type(pipe).__name__
        if class_name not in (T2V_CLASS, I2V_CLASS):
            raise ProviderUnavailableError(f"'{self.key}' loaded a {class_name}, expected a Wan pipeline.")
        applied = apply_pipeline_optimizations(pipe, profile, device.device)
        vae = getattr(pipe, "vae", None)
        if (
            vae is not None
            and profile is not PerformanceProfile.PERFORMANCE
            and callable(getattr(vae, "enable_tiling", None))
        ):
            vae.enable_tiling()  # decoding 121 frames at 720p is the VRAM peak on 16 GB cards
            applied.append("vae.enable_tiling")
        self._pipes = {class_name: pipe}
        transformer = getattr(pipe, "transformer", None) or getattr(pipe, "transformer_2", None)
        patch = getattr(getattr(transformer, "config", None), "patch_size", None)
        spatial = getattr(pipe, "vae_scale_factor_spatial", None)
        if patch and spatial:
            self._size_multiple = int(spatial) * int(patch[1])
        temporal = getattr(pipe, "vae_scale_factor_temporal", None)
        if temporal:
            self._frame_step = int(temporal)
        self._profile = profile
        self._device = device
        self._loaded = True
        logger.info("wan_loaded", extra={"model": self.key, "class": class_name, "optimizations": applied})

    def _pipe(self, class_name: str) -> Any:
        if class_name in self._pipes:
            return self._pipes[class_name]
        if not self._pipes:
            raise ProviderUnavailableError("The Wan model is not loaded.")
        import diffusers

        base = next(iter(self._pipes.values()))
        pipe = getattr(diffusers, class_name).from_pipe(base)
        self._pipes[class_name] = pipe
        return pipe

    def unload(self) -> None:
        self._pipes = {}
        self._loaded = False

    # ------------------------------------------------------------------ inference

    def generate(self, request: VideoRequest, output: Path, ctx: GenerationContext) -> Path:
        import torch

        ffmpeg = require_binary("ffmpeg", self.settings.ffmpeg_path)
        size = (request.width, request.height)
        steps = max(1, request.steps)

        def on_step(_pipe: Any, step: int, _timestep: Any, callback_kwargs: dict[str, Any]) -> dict[str, Any]:
            ctx.progress(0.9 * (step + 1) / steps)  # raises JobCancelled to abort
            return callback_kwargs

        motion = MOTION_TEXT.get(request.motion, "")
        kwargs: dict[str, Any] = {
            "prompt": f"{request.prompt}. {motion}" if motion else request.prompt,
            "negative_prompt": request.negative_prompt or DEFAULT_NEGATIVE,
            "height": request.height,
            "width": request.width,
            "num_frames": request.num_frames,
            "num_inference_steps": request.steps,
            "guidance_scale": request.guidance_scale
            if request.guidance_scale is not None
            else self.capabilities().default_guidance,
            "generator": torch.Generator(device="cpu").manual_seed(request.seed),
            "output_type": "pil",
            "callback_on_step_end": on_step,
        }
        if request.image is not None:
            pipe = self._pipe(I2V_CLASS)
            kwargs["image"] = _open_rgb(request.image, size)
            if request.last_image is not None:
                kwargs["last_image"] = _open_rgb(request.last_image, size)
        else:
            pipe = self._pipe(T2V_CLASS)
        frames = pipe(**kwargs).frames[0]
        frames_dir = ctx.temp_dir / "wan_frames"
        count = write_frames(frames, frames_dir)
        return encode_png_sequence(
            ffmpeg,
            frames_dir,
            request.fps,
            output,
            ctx.run_subprocess,
            lambda f: ctx.progress(0.9 + 0.1 * f),
            count,
        )
