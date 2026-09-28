"""Background removal with rembg's ONNX sessions (BiRefNet, ISNet, U2Net) — runs locally via onnxruntime.

Verified against rembg 2.0.85: `rembg.new_session(name)` builds the session and downloads
`<name>.onnx` from the rembg GitHub releases if it is missing; `session.predict(pil_rgb)` returns
`[mask_L]` resized to the input size. Remote sessions (e.g. `withoutbg`) are refused.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PIL.Image import Image

from app.core.config import PerformanceProfile, Settings
from app.core.errors import ProviderUnavailableError
from app.providers.base import (
    Availability,
    GenerationContext,
    ProviderStatus,
    SegmentationCapabilities,
    SegmentationProvider,
)
from app.providers.catalog import missing_packages
from app.providers.device import DeviceInfo


def rembg_home(settings: Settings) -> Path:
    """Mirror rembg's model root: U2NET_HOME wins, else REMBG_HOME, which we set to MODELS_DIR/rembg."""
    if legacy := os.environ.get("U2NET_HOME"):
        return Path(legacy).expanduser()
    return settings.models_dir / "rembg"


def onnx_candidates(session_name: str, settings: Settings) -> list[Path]:
    home = rembg_home(settings)
    fname = f"{session_name}.onnx"
    return [home / "models" / session_name / fname, home / fname]


class RembgSegmentationProvider(SegmentationProvider):
    required_packages = ("rembg", "onnxruntime")

    @property
    def session_name(self) -> str:
        name = self.spec.option("session")
        if not isinstance(name, str) or not name:
            raise ProviderUnavailableError(f"models.yaml entry '{self.key}' needs a rembg `session` name.")
        return name

    def availability(self) -> Availability:
        missing = missing_packages(self.required_packages)
        if missing:
            return Availability(
                ProviderStatus.NOT_INSTALLED, f"Missing Python packages: {', '.join(missing)}"
            )
        if any(p.is_file() for p in onnx_candidates(self.session_name, self.settings)):
            return Availability(ProviderStatus.AVAILABLE)
        hint = "offline mode" if self.settings.offline_mode else "run backend/scripts/download_models.py"
        return Availability(
            ProviderStatus.MODEL_MISSING,
            f"{self.session_name}.onnx not found under {rembg_home(self.settings)} ({hint}).",
        )

    def capabilities(self) -> SegmentationCapabilities:
        return SegmentationCapabilities(alpha_matting=False)

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        import onnxruntime
        from rembg import new_session
        from rembg.sessions import sessions

        cls = sessions.get(self.session_name)
        if cls is None:
            raise ProviderUnavailableError(f"rembg has no session '{self.session_name}'.")
        if not cls.is_local() or cls.requires_credentials():
            raise ProviderUnavailableError(f"rembg session '{self.session_name}' is not local; refusing.")
        providers = ["CPUExecutionProvider"]
        if device.device == "cuda" and "CUDAExecutionProvider" in onnxruntime.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        if not os.environ.get("U2NET_HOME"):
            os.environ["REMBG_HOME"] = str(rembg_home(self.settings))
        self._session: Any = new_session(self.session_name, providers=providers)
        self._loaded = True

    def unload(self) -> None:
        self._session = None
        self._loaded = False

    def segment(self, image: Image, ctx: GenerationContext) -> Image:
        ctx.progress(0.1)
        masks = self._session.predict(image.convert("RGB"))
        mask: Image = masks[0].convert("L")
        if mask.size != image.size:
            mask = mask.resize(image.size)
        ctx.progress(1.0)
        return mask
