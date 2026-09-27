from __future__ import annotations

from typing import Any, ClassVar

import pytest

from app.core.config import PerformanceProfile, Settings
from app.core.errors import ModelLoadError, VramOutOfMemoryError
from app.providers.base import (
    Availability,
    GenerationContext,
    ImageCapabilities,
    ImageGenerationProvider,
    ImageRequest,
    ProviderKind,
    ProviderStatus,
)
from app.providers.catalog import parse_models_config
from app.providers.device import DeviceInfo
from app.providers.memory import apply_pipeline_optimizations
from app.providers.model_manager import ModelManager
from app.providers.registry import IMPLEMENTED, ProviderRegistry

EVENTS: list[str] = []


class Tracked(ImageGenerationProvider):
    heavy: ClassVar[bool] = True

    def availability(self) -> Availability:
        return Availability(ProviderStatus.AVAILABLE)

    def capabilities(self) -> ImageCapabilities:
        return ImageCapabilities()

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        if self.spec.option("fail_load"):
            raise OSError("corrupt safetensors /secret/path")
        EVENTS.append(f"load:{self.key}")
        self._loaded = True

    def unload(self) -> None:
        EVENTS.append(f"unload:{self.key}")
        self._loaded = False

    def generate(self, request: ImageRequest, ctx: GenerationContext) -> list[Any]:
        raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")


@pytest.fixture
def manager(settings: Settings) -> Any:
    EVENTS.clear()
    IMPLEMENTED["tracked"] = Tracked
    config = parse_models_config(
        {
            "image": {
                "default": "a",
                "models": {
                    "a": {"provider": "tracked"},
                    "b": {"provider": "tracked"},
                    "broken": {"provider": "tracked", "fail_load": True},
                },
            }
        }
    )
    registry = ProviderRegistry(settings, config=config)

    def make(profile: PerformanceProfile = PerformanceProfile.BALANCED) -> ModelManager:
        return ModelManager(registry, DeviceInfo(device="cpu", dtype="float32"), profile)

    yield make
    IMPLEMENTED.pop("tracked")


def test_heavy_slot_swaps_models(manager: Any) -> None:
    mm = manager()
    with mm.use(ProviderKind.IMAGE, Tracked, "a"):
        pass
    with mm.use(ProviderKind.IMAGE, Tracked, "a"):
        pass  # cached, no reload
    with mm.use(ProviderKind.IMAGE, Tracked, "b"):
        pass
    assert EVENTS == ["load:a", "unload:a", "load:b"]
    mm.unload_all()
    assert EVENTS[-1] == "unload:b"


def test_low_vram_unloads_after_each_use(manager: Any) -> None:
    mm = manager(PerformanceProfile.LOW_VRAM)
    with mm.use(ProviderKind.IMAGE, Tracked, "a"):
        pass
    assert EVENTS == ["load:a", "unload:a"]
    assert mm.loaded_keys == []


def test_oom_is_translated(manager: Any) -> None:
    mm = manager()
    with pytest.raises(VramOutOfMemoryError), mm.use(ProviderKind.IMAGE, Tracked, "a") as provider:
        provider.generate(ImageRequest(prompt="x", width=64, height=64, steps=1, seed=0), None)  # type: ignore[arg-type]


def test_load_failure_is_translated(manager: Any) -> None:
    mm = manager()
    with pytest.raises(ModelLoadError) as info, mm.use(ProviderKind.IMAGE, Tracked, "broken"):
        pass
    assert "secret" not in info.value.message


class _Vae:
    def __init__(self) -> None:
        self.tiled = False

    def enable_tiling(self) -> None:
        self.tiled = True


class _Pipe:
    def __init__(self, methods: set[str]) -> None:
        self.calls: list[str] = []
        self.vae = _Vae()
        for name in methods:
            setattr(self, name, lambda n=name: self.calls.append(n))

    def to(self, device: str) -> None:
        self.calls.append(f"to:{device}")


@pytest.mark.parametrize(
    ("profile", "methods", "expected"),
    [
        (PerformanceProfile.PERFORMANCE, {"enable_model_cpu_offload"}, ["to_cuda"]),
        (PerformanceProfile.BALANCED, {"enable_model_cpu_offload"}, ["enable_model_cpu_offload"]),
        (PerformanceProfile.BALANCED, set(), ["to_cuda"]),
        (
            PerformanceProfile.LOW_VRAM,
            {"enable_sequential_cpu_offload", "enable_attention_slicing"},
            ["enable_sequential_cpu_offload", "vae.enable_tiling", "enable_attention_slicing"],
        ),
    ],
)
def test_optimizations_only_use_existing_methods(
    profile: PerformanceProfile, methods: set[str], expected: list[str]
) -> None:
    pipe = _Pipe(methods)
    assert apply_pipeline_optimizations(pipe, profile, "cuda") == expected


def test_no_optimizations_on_cpu() -> None:
    assert (
        apply_pipeline_optimizations(_Pipe({"enable_model_cpu_offload"}), PerformanceProfile.BALANCED, "cpu")
        == []
    )
