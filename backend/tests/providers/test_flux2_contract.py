"""Contract tests for Flux2DiffusersProvider.

No GPU/torch here, so `torch` and `diffusers` are replaced with stubs that mirror the call
signature verified in diffusers v0.40.0 (`Flux2KleinPipeline.__call__`). These tests check that
the provider calls that API correctly; they do not prove the real model runs.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.core.config import PerformanceProfile, Settings
from app.core.errors import FileInvalidError, ProviderUnavailableError, VramOutOfMemoryError
from app.providers.base import GenerationContext, ImageRequest
from app.providers.catalog import ModelSpec
from app.providers.device import DeviceInfo
from app.providers.image.flux2_diffusers import Flux2DiffusersProvider
from app.providers.memory import translate_gpu_errors

CALLS: dict[str, Any] = {}


class _Generator:
    def __init__(self, device: str) -> None:
        self.device = device
        self.seed: int | None = None

    def manual_seed(self, seed: int) -> _Generator:
        self.seed = seed
        return self


class _Pipe:
    def __init__(self, distilled: bool) -> None:
        self.config = types.SimpleNamespace(is_distilled=distilled)
        self.offloaded = False

    @classmethod
    def from_pretrained(cls, source: str, **kwargs: Any) -> _Pipe:
        CALLS["from_pretrained"] = {"source": source, **kwargs}
        return cls(distilled=CALLS.get("distilled", True))

    def enable_model_cpu_offload(self) -> None:
        self.offloaded = True

    def to(self, device: str) -> _Pipe:
        return self

    def __call__(self, **kwargs: Any) -> Any:
        CALLS["call"] = kwargs
        if CALLS.get("oom"):
            raise RuntimeError("CUDA out of memory. Tried to allocate 1.00 GiB")
        callback = kwargs["callback_on_step_end"]
        for step in range(kwargs["num_inference_steps"]):
            out = callback(self, step, 1000 - step, {"latents": "L"})
            assert out == {"latents": "L"}
        size = (kwargs["width"], kwargs["height"])
        return types.SimpleNamespace(
            images=[Image.new("RGB", size) for _ in range(kwargs["num_images_per_prompt"])]
        )


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    CALLS.clear()
    torch = types.ModuleType("torch")
    torch.bfloat16 = "bf16"  # type: ignore[attr-defined]
    torch.float32 = "fp32"  # type: ignore[attr-defined]
    torch.Generator = _Generator  # type: ignore[attr-defined]
    torch.inference_mode = nullcontext  # type: ignore[attr-defined]
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)  # type: ignore[attr-defined]
    diffusers = types.ModuleType("diffusers")
    diffusers.__version__ = "0.40.0"  # type: ignore[attr-defined]
    diffusers.Flux2KleinPipeline = _Pipe  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "diffusers", diffusers)
    yield


def _provider(settings: Settings, **spec: Any) -> Flux2DiffusersProvider:
    base = {
        "provider": "flux2_diffusers",
        "pipeline_class": "Flux2KleinPipeline",
        "repo_id": "black-forest-labs/FLUX.2-klein-4B",
        "distilled": True,
        "default_steps": 4,
        "max_reference_images": 4,
    }
    return Flux2DiffusersProvider("flux2_klein_4b", ModelSpec(**{**base, **spec}), settings)


def _ctx(tmp_path: Path, seen: list[float]) -> GenerationContext:
    return GenerationContext(temp_dir=tmp_path, progress=seen.append, run_subprocess=None)  # type: ignore[arg-type]


CUDA = DeviceInfo(device="cuda", dtype="bfloat16")


def test_load_uses_verified_arguments(stubs: None, settings: Settings) -> None:
    provider = _provider(settings, revision="abc123")
    provider.load(CUDA, PerformanceProfile.BALANCED)
    assert CALLS["from_pretrained"] == {
        "source": "black-forest-labs/FLUX.2-klein-4B",
        "torch_dtype": "bf16",
        "revision": "abc123",
        "local_files_only": False,
    }
    assert provider._pipe.offloaded is True
    assert provider.loaded


def test_offline_mode_and_local_path(stubs: None, settings: Settings, tmp_path: Path) -> None:
    offline = settings.model_copy(update={"offline_mode": True})
    provider = _provider(offline, local_path=str(tmp_path))
    provider.load(CUDA, PerformanceProfile.PERFORMANCE)
    assert CALLS["from_pretrained"]["source"] == str(tmp_path)
    assert CALLS["from_pretrained"]["local_files_only"] is True


def test_generate_maps_request_to_pipeline_call(stubs: None, settings: Settings, tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    Image.new("RGBA", (64, 64)).save(ref)
    provider = _provider(settings)
    provider.load(CUDA, PerformanceProfile.BALANCED)
    seen: list[float] = []
    request = ImageRequest(
        prompt="adult woman portrait", width=768, height=1360, steps=4, seed=10, num_images=2,
        guidance_scale=4.0, reference_images=[ref],
    )  # fmt: skip
    images = provider.generate(request, _ctx(tmp_path, seen))

    call = CALLS["call"]
    assert (call["prompt"], call["width"], call["height"]) == ("adult woman portrait", 768, 1360)
    assert call["num_inference_steps"] == 4 and call["num_images_per_prompt"] == 2
    assert [g.seed for g in call["generator"]] == [10, 11]
    assert all(g.device == "cpu" for g in call["generator"])
    assert [im.mode for im in call["image"]] == ["RGB"]
    assert "guidance_scale" not in call  # distilled checkpoint: CFG disabled
    assert "negative_prompt" not in call
    assert seen == [0.25, 0.5, 0.75, 1.0]
    assert [im.size for im in images] == [(768, 1360), (768, 1360)]


def test_guidance_passed_for_base_model(stubs: None, settings: Settings, tmp_path: Path) -> None:
    CALLS["distilled"] = False
    provider = _provider(settings, distilled=False)
    provider.load(CUDA, PerformanceProfile.BALANCED)
    assert provider.capabilities().guidance is True
    provider.generate(ImageRequest(prompt="x", width=512, height=512, steps=2, seed=0, guidance_scale=3.5),
                      _ctx(tmp_path, []))  # fmt: skip
    assert CALLS["call"]["guidance_scale"] == 3.5
    assert "image" not in CALLS["call"]


def test_config_is_distilled_overrides_catalog(stubs: None, settings: Settings) -> None:
    CALLS["distilled"] = False
    provider = _provider(settings, distilled=True)
    assert provider.capabilities().guidance is False
    provider.load(CUDA, PerformanceProfile.BALANCED)
    assert provider.capabilities().guidance is True


def test_cancel_from_step_callback_aborts(stubs: None, settings: Settings, tmp_path: Path) -> None:
    provider = _provider(settings)
    provider.load(CUDA, PerformanceProfile.BALANCED)

    class Cancelled(Exception):
        pass

    def progress(fraction: float) -> None:
        if fraction >= 0.5:
            raise Cancelled

    ctx = GenerationContext(temp_dir=tmp_path, progress=progress, run_subprocess=None)  # type: ignore[arg-type]
    with pytest.raises(Cancelled):
        provider.generate(ImageRequest(prompt="x", width=512, height=512, steps=4, seed=0), ctx)


def test_oom_maps_to_vram_error(stubs: None, settings: Settings, tmp_path: Path) -> None:
    provider = _provider(settings)
    provider.load(CUDA, PerformanceProfile.BALANCED)
    CALLS["oom"] = True
    with pytest.raises(VramOutOfMemoryError), translate_gpu_errors():
        provider.generate(
            ImageRequest(prompt="x", width=512, height=512, steps=1, seed=0), _ctx(tmp_path, [])
        )


def test_missing_pipeline_class(stubs: None, settings: Settings) -> None:
    provider = _provider(settings, pipeline_class="Flux2FuturePipeline")
    with pytest.raises(ProviderUnavailableError, match=r"diffusers>=0\.40\.0"):
        provider.load(CUDA, PerformanceProfile.BALANCED)


def test_bad_reference_image(stubs: None, settings: Settings, tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    provider = _provider(settings)
    provider.load(CUDA, PerformanceProfile.BALANCED)
    with pytest.raises(FileInvalidError):
        provider.generate(
            ImageRequest(prompt="x", width=512, height=512, steps=1, seed=0, reference_images=[bad]),
            _ctx(tmp_path, []),
        )


def test_generate_requires_load(settings: Settings, tmp_path: Path) -> None:
    with pytest.raises(ProviderUnavailableError):
        _provider(settings).generate(
            ImageRequest(prompt="x", width=64, height=64, steps=1, seed=0), _ctx(tmp_path, [])
        )


def test_capabilities_from_catalog(settings: Settings) -> None:
    caps = _provider(settings).capabilities()
    assert (caps.max_reference_images, caps.default_steps, caps.size_multiple) == (4, 4, 16)
    assert caps.negative_prompt is False and caps.inpainting is False
