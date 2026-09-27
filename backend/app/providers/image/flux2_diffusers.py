"""FLUX.2 image provider via Diffusers (`Flux2KleinPipeline`, `Flux2Pipeline`).

API facts used here were read from diffusers v0.40.0 source (see docs/PHASE0_VALIDATION.md):
- `image=` accepts a list of PIL images (multi-reference); output size must be a multiple of 16.
- CFG applies only when `guidance_scale > 1` and the checkpoint is not distilled; the negative
  prompt is fixed to "" by the pipeline (no string parameter).
- `callback_on_step_end(pipe, step, timestep, callback_kwargs) -> dict`; raising inside it aborts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PIL import Image

from app.core.config import PerformanceProfile
from app.core.errors import FileInvalidError, ProviderUnavailableError
from app.providers.base import GenerationContext, ImageCapabilities, ImageGenerationProvider, ImageRequest
from app.providers.catalog import resolve_local_path
from app.providers.device import DeviceInfo
from app.providers.memory import apply_pipeline_optimizations

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

logger = logging.getLogger(__name__)

SIZE_MULTIPLE = 16
MIN_DIFFUSERS = "0.40.0"


class Flux2DiffusersProvider(ImageGenerationProvider):
    required_packages = ("torch", "diffusers", "transformers", "accelerate")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pipe: Any = None
        self._distilled: bool | None = None

    # ------------------------------------------------------------------ metadata

    @property
    def distilled(self) -> bool:
        if self._distilled is not None:
            return self._distilled
        return bool(self.spec.option("distilled", False))

    def capabilities(self) -> ImageCapabilities:
        return ImageCapabilities(
            text_to_image=True,
            image_edit=True,
            max_reference_images=int(self.spec.option("max_reference_images", 0)),
            inpainting=False,  # Flux2KleinInpaintPipeline wiring arrives with Image Studio (Phase 7)
            negative_prompt=False,
            guidance=not self.distilled,
            min_size=256,
            max_size=int(self.spec.option("max_size", 2048)),
            size_multiple=SIZE_MULTIPLE,
            max_images_per_request=4,
            default_steps=int(self.spec.option("default_steps", 28)),
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

        class_name = self.spec.pipeline_class or "Flux2KleinPipeline"
        pipeline_cls = getattr(diffusers, class_name, None)
        if pipeline_cls is None:
            raise ProviderUnavailableError(
                f"diffusers {getattr(diffusers, '__version__', '?')} has no {class_name}; "
                f"install diffusers>={MIN_DIFFUSERS}."
            )
        dtype = getattr(torch, device.dtype)
        pipe = pipeline_cls.from_pretrained(
            self.model_source(),
            torch_dtype=dtype,
            revision=self.spec.revision,
            local_files_only=self.settings.offline_mode,
        )
        applied = apply_pipeline_optimizations(pipe, profile, device.device)
        if device.device == "cpu":
            logger.warning("flux2_on_cpu", extra={"model": self.key})
        config = getattr(pipe, "config", None)
        self._distilled = bool(getattr(config, "is_distilled", self.spec.option("distilled", False)))
        self._pipe = pipe
        self._loaded = True
        logger.info(
            "flux2_loaded", extra={"model": self.key, "optimizations": applied, "distilled": self._distilled}
        )

    def unload(self) -> None:
        self._pipe = None
        self._loaded = False

    # ------------------------------------------------------------------ inference

    def generate(self, request: ImageRequest, ctx: GenerationContext) -> list[PILImage]:
        if self._pipe is None:
            raise ProviderUnavailableError("The FLUX.2 model is not loaded.")
        import torch

        references = [_open_rgb(path) for path in request.reference_images]
        generators = [
            torch.Generator(device="cpu").manual_seed(request.seed + i) for i in range(request.num_images)
        ]
        total = max(1, request.steps)

        def on_step(_pipe: Any, step: int, _timestep: Any, callback_kwargs: dict[str, Any]) -> dict[str, Any]:
            ctx.progress((step + 1) / total)  # raises JobCancelled / WorkerStopping to abort
            return callback_kwargs

        kwargs: dict[str, Any] = {
            "prompt": request.prompt,
            "height": request.height,
            "width": request.width,
            "num_inference_steps": request.steps,
            "num_images_per_prompt": request.num_images,
            "generator": generators,
            "callback_on_step_end": on_step,
        }
        if references:
            kwargs["image"] = references
        if request.guidance_scale is not None and not self.distilled:
            kwargs["guidance_scale"] = request.guidance_scale

        with torch.inference_mode():
            result = self._pipe(**kwargs)
        return list(result.images)


def _open_rgb(path: Any) -> PILImage:
    try:
        with Image.open(path) as img:
            return img.convert("RGB")
    except OSError as exc:
        raise FileInvalidError("A reference image could not be read.") from exc
