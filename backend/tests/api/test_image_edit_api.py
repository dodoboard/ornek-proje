"""Image Studio editing: instruction edit, inpaint and outpaint through API + worker (dev provider)."""

from __future__ import annotations

import io
import random
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageChops, ImageDraw

from app.core.config import Settings
from app.main import create_app
from app.providers.device import DeviceInfo
from app.workers.queue import JobQueue
from app.workers.registry import default_registry
from app.workers.runner import Worker


def _noise_png(size: tuple[int, int], seed: int = 1) -> bytes:
    rng = random.Random(seed)
    img = Image.frombytes("RGB", size, bytes(rng.randrange(256) for _ in range(size[0] * size[1] * 3)))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _mask_png(size: tuple[int, int], box: tuple[int, int, int, int]) -> bytes:
    mask = Image.new("RGB", size, (0, 0, 0))
    ImageDraw.Draw(mask).rectangle(box, fill=(255, 255, 255))
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def dev_client(settings: Settings) -> Iterator[TestClient]:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with TestClient(create_app(dev), raise_server_exceptions=False) as client:
        client.patch("/api/settings", json={"default_models": {"image": "dev_fake_image"}})
        yield client


def _upload(client: TestClient, data: bytes, name: str = "img.png") -> str:
    response = client.post("/api/assets", files={"file": (name, data, "image/png")})
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["id"]
    return asset_id


def _run(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/generate/image-edit", json=body)
    assert response.status_code == 202, response.text
    app: Any = client.app
    worker = Worker(
        app.state.settings, JobQueue(app.state.session_factory), default_registry(),
        device=DeviceInfo(device="cpu", dtype="float32"),
    )  # fmt: skip
    worker.run_once()
    worker.shutdown()
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "completed", job
    generation: dict[str, Any] = client.get(f"/api/generations/{job['result']['generation_id']}").json()
    return generation


def _image(client: TestClient, asset_id: str) -> Image.Image:
    return Image.open(io.BytesIO(client.get(f"/api/assets/{asset_id}/content").content)).convert("RGB")


def test_inpaint_changes_only_the_masked_area(dev_client: TestClient) -> None:
    source_bytes = _noise_png((320, 256))
    source_id = _upload(dev_client, source_bytes)
    box = (100, 80, 220, 180)
    mask_id = _upload(dev_client, _mask_png((320, 256), box), "mask.png")

    generation = _run(
        dev_client,
        {"mode": "inpaint", "source_asset_id": source_id, "mask_asset_id": mask_id,
         "prompt": "a glass perfume bottle", "steps": 2, "seed": 9, "feather": 4},
    )  # fmt: skip
    assert generation["kind"] == "image_edit"
    assert generation["params"]["mode"] == "inpaint" and generation["params"]["strength"] == 0.9
    assert generation["input_asset_ids"][:2] == [source_id, mask_id]
    [asset] = generation["assets"]
    assert asset["metadata"]["ai_edited"] is True and asset["metadata"]["edit_mode"] == "inpaint"

    result = _image(dev_client, asset["id"])
    original = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    assert result.size == original.size
    diff = ImageChops.difference(result, original).convert("L")
    outside = Image.new("L", original.size, 255)
    ImageDraw.Draw(outside).rectangle(box, fill=0)
    assert ImageChops.multiply(diff, outside).getbbox() is None  # byte-exact outside the mask
    assert diff.crop((140, 110, 180, 150)).getbbox() is not None  # inside actually changed


def test_outpaint_extends_canvas_and_keeps_original(dev_client: TestClient) -> None:
    source_bytes = _noise_png((256, 256), seed=2)
    source_id = _upload(dev_client, source_bytes)
    generation = _run(
        dev_client,
        {"mode": "outpaint", "source_asset_id": source_id, "prompt": "wider beach scene",
         "padding": {"left": 64, "right": 64, "bottom": 32}, "steps": 2, "feather": 0},
    )  # fmt: skip
    result = _image(dev_client, generation["assets"][0]["id"])
    assert result.size == (384, 288)
    original = Image.open(io.BytesIO(source_bytes)).convert("RGB")
    # The interior (outside the 16 px overlap band on extended sides) is untouched.
    interior = (64 + 16, 0, 64 + 256 - 16, 256 - 16)
    assert result.crop(interior).tobytes() == original.crop((16, 0, 240, 240)).tobytes()
    assert generation["params"]["padding"] == {"left": 64, "top": 0, "right": 64, "bottom": 32}


def test_instruction_edit_uses_source_as_first_reference(dev_client: TestClient) -> None:
    source_id = _upload(dev_client, _noise_png((256, 320), seed=3))
    ref_id = _upload(dev_client, _noise_png((64, 64), seed=4))
    generation = _run(
        dev_client,
        {"mode": "edit", "source_asset_id": source_id, "reference_asset_ids": [ref_id],
         "prompt": "make it night time", "steps": 1},
    )  # fmt: skip
    assert generation["input_asset_ids"] == [source_id, ref_id]
    assert (generation["params"]["width"], generation["params"]["height"]) == (256, 320)
    assert generation["params"]["strength"] is None


def test_generation_listing_filters_multiple_kinds(dev_client: TestClient) -> None:
    source_id = _upload(dev_client, _noise_png((256, 256), seed=5))
    edit = _run(dev_client, {"mode": "edit", "source_asset_id": source_id, "prompt": "add snow", "steps": 1})

    def ids(kind: str) -> list[str]:
        items = dev_client.get("/api/generations", params={"kind": kind}).json()["items"]
        return [g["id"] for g in items]

    assert ids("image_edit") == [edit["id"]]
    assert ids("image") == []
    assert ids("image,image_edit") == [edit["id"]]


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"mode": "inpaint"}, 422, "VALIDATION_ERROR"),  # no mask
        ({"mode": "outpaint"}, 422, "VALIDATION_ERROR"),  # no padding
        ({"mode": "outpaint", "padding": {"left": 10}}, 422, "VALIDATION_ERROR"),  # not multiple of 16
        ({"mode": "outpaint", "padding": {"left": 0}}, 422, "VALIDATION_ERROR"),  # extends nothing
        ({"mode": "outpaint", "padding": {"left": 1024, "right": 1024}}, 422, "INVALID_GENERATION_REQUEST"),
        ({"mode": "edit", "strength": 0.5}, 422, "VALIDATION_ERROR"),
        ({"mode": "edit", "reference_asset_ids": ["A", "B", "C", "D"]}, 422, "INVALID_GENERATION_REQUEST"),
        ({"mode": "edit", "prompt": "turn her into a schoolgirl"}, 422, "VALIDATION_ERROR"),
        ({"mode": "inpaint", "mask_asset_id": "AST_missing"}, 404, "NOT_FOUND"),
    ],
)
def test_edit_validation(dev_client: TestClient, body: dict[str, Any], status: int, code: str) -> None:
    source_id = _upload(dev_client, _noise_png((256, 256)))
    payload = {"source_asset_id": source_id, "prompt": "x", **body}
    response = dev_client.post("/api/generate/image-edit", json=payload)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert dev_client.get("/api/jobs").json()["total"] == 0


def test_mask_must_be_an_image(dev_client: TestClient, make_media: Any) -> None:
    import shutil

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    source_id = _upload(dev_client, _noise_png((256, 256)))
    audio = dev_client.post("/api/assets", files={"file": ("t.wav", make_media("wav"), "audio/wav")}).json()
    response = dev_client.post(
        "/api/generate/image-edit",
        json={"mode": "inpaint", "source_asset_id": source_id, "mask_asset_id": audio["id"], "prompt": "x"},
    )
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"
