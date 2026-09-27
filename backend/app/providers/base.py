"""Provider abstraction. These are *our* interfaces; implementations wrap real library APIs only.

Every provider must be importable without its heavy dependencies (torch, diffusers, ...):
heavy imports happen inside `load()`.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from PIL.Image import Image

    from app.core.config import PerformanceProfile, Settings
    from app.providers.catalog import ModelSpec
    from app.providers.device import DeviceInfo


class ProviderKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    LLM = "llm"
    TTS = "tts"
    LIPSYNC = "lipsync"
    ASR = "asr"
    SEGMENTATION = "segmentation"
    UPSCALE = "upscale"


class ProviderStatus(StrEnum):
    AVAILABLE = "available"
    MODEL_MISSING = "model_missing"
    NOT_INSTALLED = "not_installed"
    NOT_IMPLEMENTED = "not_implemented"
    DISABLED = "disabled"


class Maturity(StrEnum):
    STABLE = "stable"
    EXPERIMENTAL = "experimental"
    DEV_ONLY = "dev_only"


@dataclass(frozen=True)
class Availability:
    status: ProviderStatus
    detail: str | None = None


# --------------------------------------------------------------------------- capabilities


class Capabilities(BaseModel):
    pass


class ImageCapabilities(Capabilities):
    text_to_image: bool = True
    image_edit: bool = False
    max_reference_images: int = 0
    inpainting: bool = False
    negative_prompt: bool = False
    guidance: bool = False
    min_size: int = 256
    max_size: int = 2048
    size_multiple: int = 16
    max_images_per_request: int = 4
    default_steps: int = 28


class VideoCapabilities(Capabilities):
    image_to_video: bool = True
    text_to_video: bool = False
    last_frame_conditioning: bool = False
    negative_prompt: bool = False
    guidance: bool = False
    fps: tuple[int, ...] = (24,)
    max_frames: int = 121
    size_multiple: int = 16
    default_steps: int = 30


class LLMCapabilities(Capabilities):
    json_schema_output: bool = False
    languages: tuple[str, ...] = ()


class TTSCapabilities(Capabilities):
    languages: tuple[str, ...] = ()
    voice_cloning: bool = False
    speed_control: bool = False


class LipSyncCapabilities(Capabilities):
    accepts_image: bool = False
    accepts_video: bool = True


class ASRCapabilities(Capabilities):
    word_timestamps: bool = False
    languages: tuple[str, ...] = ()


class SegmentationCapabilities(Capabilities):
    alpha_matting: bool = False


class UpscaleCapabilities(Capabilities):
    scales: tuple[int, ...] = (4,)


# --------------------------------------------------------------------------- runtime context


ProgressCallback = Callable[[float], None]
SubprocessRunner = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass
class GenerationContext:
    """What a provider may use while generating. `progress(0..1)` raises if the job was cancelled."""

    temp_dir: Path
    progress: ProgressCallback
    run_subprocess: SubprocessRunner


# --------------------------------------------------------------------------- base provider


class Provider(ABC):
    kind: ClassVar[ProviderKind]
    maturity: ClassVar[Maturity] = Maturity.STABLE
    is_local: ClassVar[bool] = True
    #: Heavy providers share a single GPU slot in the ModelManager.
    heavy: ClassVar[bool] = True
    #: Import names that must be installed for this provider to work.
    required_packages: ClassVar[tuple[str, ...]] = ()

    def __init__(self, key: str, spec: ModelSpec, settings: Settings) -> None:
        self.key = key
        self.spec = spec
        self.settings = settings
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def availability(self) -> Availability:
        """Cheap check (no heavy imports): packages installed and weights present."""
        from app.providers.catalog import missing_packages, weights_status

        missing = missing_packages(self.required_packages)
        if missing:
            return Availability(
                ProviderStatus.NOT_INSTALLED, f"Missing Python packages: {', '.join(missing)}"
            )
        return weights_status(self.spec, self.settings)

    @abstractmethod
    def capabilities(self) -> Capabilities: ...

    @abstractmethod
    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None: ...

    @abstractmethod
    def unload(self) -> None: ...


# --------------------------------------------------------------------------- kind-specific interfaces


@dataclass
class ImageRequest:
    prompt: str
    width: int
    height: int
    steps: int
    seed: int
    num_images: int = 1
    guidance_scale: float | None = None
    negative_prompt: str | None = None
    reference_images: list[Path] = field(default_factory=list)


@dataclass
class InpaintRequest(ImageRequest):
    """Repaint the white area of `mask` inside `image`; `reference_images` condition the new content."""

    image: Path | None = None
    mask: Path | None = None
    strength: float = 1.0


class ImageGenerationProvider(Provider):
    kind = ProviderKind.IMAGE

    @abstractmethod
    def capabilities(self) -> ImageCapabilities: ...

    @abstractmethod
    def generate(self, request: ImageRequest, ctx: GenerationContext) -> list[Image]: ...

    def inpaint(self, request: InpaintRequest, ctx: GenerationContext) -> list[Image]:
        from app.core.errors import ProviderUnavailableError

        raise ProviderUnavailableError("This image model does not support inpainting.")


@dataclass
class VideoRequest:
    prompt: str
    width: int
    height: int
    num_frames: int
    fps: int
    steps: int
    seed: int
    image: Path | None = None
    last_image: Path | None = None
    guidance_scale: float | None = None
    negative_prompt: str | None = None


class VideoGenerationProvider(Provider):
    kind = ProviderKind.VIDEO

    @abstractmethod
    def capabilities(self) -> VideoCapabilities: ...

    @abstractmethod
    def generate(self, request: VideoRequest, output: Path, ctx: GenerationContext) -> Path:
        """Write an MP4 to `output` and return it."""


class LLMProvider(Provider):
    kind = ProviderKind.LLM
    heavy = False  # runs in its own process (e.g. Ollama); VRAM released via keep_alive

    @abstractmethod
    def capabilities(self) -> LLMCapabilities: ...

    @abstractmethod
    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


class TTSProvider(Provider):
    kind = ProviderKind.TTS

    @abstractmethod
    def capabilities(self) -> TTSCapabilities: ...

    @abstractmethod
    def synthesize(
        self, text: str, language: str, output: Path, ctx: GenerationContext, *, voice: str | None = None,
        speed: float = 1.0,
    ) -> Path: ...  # fmt: skip


class LipSyncProvider(Provider):
    kind = ProviderKind.LIPSYNC

    @abstractmethod
    def capabilities(self) -> LipSyncCapabilities: ...

    @abstractmethod
    def sync(self, face: Path, audio: Path, output: Path, ctx: GenerationContext) -> Path: ...


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


class ASRProvider(Provider):
    kind = ProviderKind.ASR
    heavy = False

    @abstractmethod
    def capabilities(self) -> ASRCapabilities: ...

    @abstractmethod
    def transcribe(self, audio: Path, language: str | None, ctx: GenerationContext) -> list[Word]: ...


class SegmentationProvider(Provider):
    kind = ProviderKind.SEGMENTATION
    heavy = False

    @abstractmethod
    def capabilities(self) -> SegmentationCapabilities: ...

    @abstractmethod
    def segment(self, image: Image, ctx: GenerationContext) -> Image:
        """Return an 8-bit 'L' alpha mask the size of `image`."""


class UpscaleProvider(Provider):
    kind = ProviderKind.UPSCALE
    heavy = False

    @abstractmethod
    def capabilities(self) -> UpscaleCapabilities: ...

    @abstractmethod
    def upscale(self, image: Image, scale: int, ctx: GenerationContext) -> Image: ...
