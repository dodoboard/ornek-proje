"""rembg segmentation provider against a stub of the verified rembg 2.0.85 API (no weights in CI)."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, ClassVar

import pytest
from PIL import Image

from app.core.config import PerformanceProfile, Settings
from app.core.errors import ProviderUnavailableError
from app.providers.base import GenerationContext, ProviderStatus
from app.providers.catalog import ModelSpec
from app.providers.device import DeviceInfo
from app.providers.segmentation import rembg_onnx
from app.providers.segmentation.rembg_onnx import RembgSegmentationProvider


class _Session:
    local = True
    created: ClassVar[list[tuple[str, list[str]]]] = []

    def __init__(self, name: str, providers: list[str]) -> None:
        self.name = name
        _Session.created.append((name, providers))

    @classmethod
    def is_local(cls) -> bool:
        return cls.local

    @classmethod
    def requires_credentials(cls) -> bool:
        return not cls.local

    def predict(self, img: Image.Image) -> list[Image.Image]:
        return [Image.new("L", (img.width // 2, img.height // 2), 200)]


@pytest.fixture
def stub_rembg(monkeypatch: pytest.MonkeyPatch) -> type[_Session]:
    _Session.created = []
    _Session.local = True
    rembg = types.ModuleType("rembg")
    rembg.new_session = lambda name, providers: _Session(name, providers)  # type: ignore[attr-defined]
    sessions = types.ModuleType("rembg.sessions")
    sessions.sessions = {"birefnet-general": _Session}  # type: ignore[attr-defined]
    ort = types.ModuleType("onnxruntime")
    ort.get_available_providers = lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    monkeypatch.setitem(sys.modules, "rembg.sessions", sessions)
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setattr(rembg_onnx, "missing_packages", lambda names: [])
    monkeypatch.delenv("U2NET_HOME", raising=False)
    return _Session


def _provider(settings: Settings, session: str = "birefnet-general") -> RembgSegmentationProvider:
    return RembgSegmentationProvider(
        "birefnet_general", ModelSpec(provider="rembg_onnx", session=session), settings
    )


def _ctx(tmp_path: Path) -> GenerationContext:
    return GenerationContext(tmp_path, lambda _: None, lambda *a, **k: None)  # type: ignore[arg-type,return-value]


def test_status_follows_the_onnx_file(settings: Settings, stub_rembg: Any) -> None:
    provider = _provider(settings)
    status = provider.availability()
    assert status.status is ProviderStatus.MODEL_MISSING
    assert "birefnet-general.onnx" in (status.detail or "")
    weights = settings.models_dir / "rembg" / "models" / "birefnet-general" / "birefnet-general.onnx"
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"onnx")
    assert provider.availability().status is ProviderStatus.AVAILABLE


def test_not_installed_without_packages(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rembg_onnx, "missing_packages", lambda names: ["rembg"])
    assert _provider(settings).availability().status is ProviderStatus.NOT_INSTALLED


def test_segment_uses_cuda_and_returns_full_size_mask(
    settings: Settings, stub_rembg: Any, tmp_path: Path
) -> None:
    provider = _provider(settings)
    provider.load(DeviceInfo(device="cuda", dtype="bfloat16"), PerformanceProfile.BALANCED)
    assert stub_rembg.created == [("birefnet-general", ["CUDAExecutionProvider", "CPUExecutionProvider"])]
    mask = provider.segment(Image.new("RGB", (64, 48)), _ctx(tmp_path))
    assert mask.mode == "L" and mask.size == (64, 48)


def test_refuses_remote_or_unknown_sessions(settings: Settings, stub_rembg: Any) -> None:
    stub_rembg.local = False
    with pytest.raises(ProviderUnavailableError, match="not local"):
        _provider(settings).load(DeviceInfo(device="cpu", dtype="float32"), PerformanceProfile.BALANCED)
    with pytest.raises(ProviderUnavailableError, match="no session"):
        _provider(settings, "withoutbg").load(
            DeviceInfo(device="cpu", dtype="float32"), PerformanceProfile.BALANCED
        )
