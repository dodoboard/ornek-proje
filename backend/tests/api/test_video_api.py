"""POST /api/generate/video through the worker: camera motion (no AI) and the dev placeholder model."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.main import create_app
from app.providers.device import DeviceInfo
from app.workers.queue import JobQueue
from app.workers.registry import default_registry
from app.workers.runner import Worker

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg not installed")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with TestClient(create_app(dev), raise_server_exceptions=False) as c:
        yield c


def _upload_png(client: TestClient, size: tuple[int, int] = (400, 300)) -> str:
    buffer = io.BytesIO()
    Image.effect_noise(size, 60).convert("RGB").save(buffer, format="PNG")
    response = client.post("/api/assets", files={"file": ("photo.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["id"]
    return asset_id


def _run(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/generate/video", json=body)
    assert response.status_code == 202, response.text
    app: Any = client.app
    worker = Worker(
        app.state.settings, JobQueue(app.state.session_factory), default_registry(),
        device=DeviceInfo(device="cpu", dtype="float32"),
    )  # fmt: skip
    worker.run_once()
    worker.shutdown()
    job: dict[str, Any] = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "completed", job
    return job


def test_camera_motion_clip_is_marked_no_ai(client: TestClient, tmp_path: Any) -> None:
    image_id = _upload_png(client)
    job = _run(
        client,
        {"model_key": "camera_motion", "image_asset_id": image_id, "width": 320, "height": 180,
         "duration_s": 1, "fps": 30, "motion": "slow_push_in"},
    )  # fmt: skip
    assert (job["result"]["num_frames"], job["result"]["fps"]) == (30, 30)
    generation = client.get(f"/api/generations/{job['result']['generation_id']}").json()
    assert generation["kind"] == "video" and generation["params"]["mode"] == "image_to_video"
    [asset] = generation["assets"]
    assert asset["kind"] == "video" and asset["ai_generated"] is False
    assert (asset["width"], asset["height"]) == (320, 180)
    assert asset["duration_s"] == pytest.approx(1.0, abs=0.05)
    assert asset["metadata"]["disclosure_label"] == "no_ai"

    content = client.get(f"/api/assets/{asset['id']}/content")
    assert content.status_code == 200
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(content.content)
    tags = json.loads(
        subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(clip)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )["format"]["tags"]
    assert json.loads(tags["comment"])["generation_id"] == generation["id"]
    thumb = client.get(f"/api/assets/{asset['id']}/thumbnail")
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    listed = client.get("/api/generations", params={"kind": "video"}).json()["items"]
    assert [g["id"] for g in listed] == [generation["id"]]


def test_dev_model_text_to_video_and_shot_link(client: TestClient) -> None:
    project = client.post("/api/projects", json={"type": "social", "name": "Clips"}).json()
    script_job = client.post(f"/api/projects/{project['id']}/script", json={"template_only": True})
    _run_script(client, script_job)
    shot = client.get(f"/api/projects/{project['id']}/storyboard").json()["shots"][0]

    job = _run(
        client,
        {"model_key": "dev_fake_video", "prompt": "adult presenter waves", "width": 160, "height": 128,
         "duration_s": 1, "fps": 24, "project_id": project["id"], "shot_id": shot["id"]},
    )  # fmt: skip
    generation = client.get(f"/api/generations/{job['result']['generation_id']}").json()
    assert generation["params"]["mode"] == "text_to_video"
    [asset] = generation["assets"]
    assert asset["metadata"]["dev_placeholder"] is True and asset["metadata"]["generated_with_ai"] is False
    updated = client.get(f"/api/projects/{project['id']}/storyboard").json()["shots"][0]
    assert updated["clip_asset_id"] == asset["id"] and updated["status"] == "clip_ready"


def _run_script(client: TestClient, response: Any) -> None:
    assert response.status_code == 202, response.text
    app: Any = client.app
    worker = Worker(app.state.settings, JobQueue(app.state.session_factory), default_registry())
    worker.run_once()
    worker.shutdown()


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"model_key": "camera_motion", "width": 320, "height": 180}, 422, "INVALID_GENERATION_REQUEST"),
        ({"model_key": "camera_motion", "image_asset_id": "AST_missing"}, 404, "NOT_FOUND"),
        ({"model_key": "wan22_ti2v_5b", "prompt": "x"}, 503, None),
        ({"prompt": "a schoolgirl dancing", "model_key": "dev_fake_video"}, 422, "VALIDATION_ERROR"),
        (
            {"model_key": "dev_fake_video", "prompt": "x", "width": 160, "height": 128, "shot_id": "SHT_x"},
            404,
            None,
        ),
    ],
)
def test_video_validation(client: TestClient, body: dict[str, Any], status: int, code: str | None) -> None:
    response = client.post("/api/generate/video", json=body)
    assert response.status_code == status, response.text
    if code:
        assert response.json()["error"]["code"] == code
