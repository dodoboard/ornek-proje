from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_models_lists_every_kind_with_status(client: TestClient) -> None:
    body = client.get("/api/models").json()
    assert body["fake_providers_enabled"] is False
    kinds = {k["kind"]: k for k in body["kinds"]}
    assert set(kinds) == {"image", "video", "llm", "tts", "lipsync", "asr", "segmentation", "upscale"}
    image = kinds["image"]
    assert image["default_key"] == "flux2_klein_4b"
    klein = next(p for p in image["providers"] if p["key"] == "flux2_klein_4b")
    # Implemented in Phase 5; this CI environment has no torch/diffusers.
    assert klein["status"] in {"not_installed", "model_missing", "available"}
    assert klein["source"] == "black-forest-labs/FLUX.2-klein-4B"
    assert klein["is_default"] is True
    assert klein["capabilities"]["negative_prompt"] is False
    assert klein["capabilities"]["guidance"] is False  # distilled
    video = kinds["video"]
    assert all(p["status"] == "not_implemented" for p in video["providers"])


def test_models_include_dev_fakes_when_enabled(settings: Settings) -> None:
    dev = settings.model_copy(update={"enable_fake_providers": True})
    with TestClient(create_app(dev)) as client:
        body = client.get("/api/models").json()
    image = next(k for k in body["kinds"] if k["kind"] == "image")
    fake = next(p for p in image["providers"] if p["key"] == "dev_fake_image")
    assert (fake["status"], fake["maturity"]) == ("available", "dev_only")
    assert fake["capabilities"]["negative_prompt"] is False


def test_settings_defaults_and_patch(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    current = client.get("/api/settings").json()
    assert current["performance_profile"] == "balanced"
    assert current["telemetry_enabled"] is False
    assert current["restart_required_fields"] == ["offline_mode"]

    weights = tmp_path / "klein9b"
    weights.mkdir()
    patched = client.patch(
        "/api/settings",
        json={
            "performance_profile": "low_vram",
            "default_models": {"image": "flux2_klein_9b"},
            "model_paths": {"flux2_klein_9b": str(weights)},
            "ai_watermark": True,
        },
    ).json()
    assert patched["performance_profile"] == "low_vram"
    assert patched["default_models"] == {"image": "flux2_klein_9b"}

    models = client.get("/api/models").json()
    image = next(k for k in models["kinds"] if k["kind"] == "image")
    assert image["default_key"] == "flux2_klein_9b"
    nine = next(p for p in image["providers"] if p["key"] == "flux2_klein_9b")
    assert nine["source"] == str(weights)

    # Removing an override restores the catalog source.
    client.patch("/api/settings", json={"model_paths": {"flux2_klein_9b": None}})
    assert client.get("/api/settings").json()["model_paths"] == {}
    assert client.get("/api/settings").json()["ai_watermark"] is True


def test_settings_validation(client: TestClient) -> None:
    assert client.patch("/api/settings", json={"default_models": {"image": "nope"}}).status_code == 422
    assert client.patch("/api/settings", json={"model_paths": {"nope": "/x"}}).status_code == 422
    assert (
        client.patch("/api/settings", json={"ffmpeg_path": "/definitely/missing/ffmpeg"}).status_code == 422
    )
    assert client.patch("/api/settings", json={"telemetry_enabled": True}).status_code == 422
    assert client.patch("/api/settings", json={"performance_profile": "turbo"}).status_code == 422


def test_ffmpeg_path_preference_is_used_by_system(client: TestClient) -> None:
    real = shutil.which("ffmpeg")
    if real is None:
        return
    client.patch("/api/settings", json={"ffmpeg_path": real})
    assert client.get("/api/system").json()["ffmpeg"]["path"] == real
    client.patch("/api/settings", json={"ffmpeg_path": ""})
    assert client.get("/api/settings").json()["ffmpeg_path"] is None


def test_worker_runtime_is_exposed(client: TestClient) -> None:
    from app.workers.queue import JobQueue

    runtime: dict[str, Any] = {"device": "cuda", "gpu_name": "RTX 5080", "arch_supported": True}
    JobQueue(client.app.state.session_factory).register_worker("WRK_1", "host", 1, runtime)  # type: ignore[attr-defined]
    assert client.get("/api/system").json()["worker"]["runtime"] == runtime
