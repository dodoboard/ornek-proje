"""Product Studio: cutout + scene jobs through API and worker (colour-key segmentation, dev image model)."""

from __future__ import annotations

import io
import json
import random
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.core.config import Settings
from app.main import create_app
from app.providers.device import DeviceInfo
from app.workers.queue import JobQueue
from app.workers.registry import default_registry
from app.workers.runner import Worker

PRODUCT_BOX = (150, 50, 250, 270)  # inclusive rectangle drawn in the photo


def _photo_png() -> bytes:
    img = Image.new("RGB", (400, 300), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle(PRODUCT_BOX, fill=(20, 60, 140))
    draw.rectangle((165, 120, 235, 200), fill=(250, 250, 250))  # white label inside the product
    rng = random.Random(7)
    for x in range(175, 225):
        for y in range(135, 185):
            img.putpixel((x, y), (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def _png(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with TestClient(create_app(dev), raise_server_exceptions=False) as c:
        c.patch(
            "/api/settings", json={"default_models": {"image": "dev_fake_image", "segmentation": "color_key"}}
        )
        yield c


def _upload(client: TestClient, data: bytes, name: str = "p.png") -> str:
    response = client.post("/api/assets", files={"file": (name, data, "image/png")})
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["id"]
    return asset_id


def _run(client: TestClient, response: Any) -> dict[str, Any]:
    assert response.status_code == 202, response.text
    app: Any = client.app
    worker = Worker(
        app.state.settings, JobQueue(app.state.session_factory), default_registry(),
        device=DeviceInfo(device="cpu", dtype="float32"),
    )  # fmt: skip
    worker.run_once()
    worker.shutdown()
    job: dict[str, Any] = client.get(f"/api/jobs/{response.json()['id']}").json()
    return job


def _image(client: TestClient, asset_id: str) -> Image.Image:
    return Image.open(io.BytesIO(client.get(f"/api/assets/{asset_id}/content").content))


@pytest.fixture
def product(client: TestClient) -> dict[str, Any]:
    product: dict[str, Any] = client.post("/api/products", json={"name": "Aurora Serum"}).json()
    photo_id = _upload(client, _photo_png())
    job = _run(
        client, client.post(f"/api/products/{product['id']}/cutout", json={"source_asset_id": photo_id})
    )
    assert job["status"] == "completed", job
    product["photo_id"] = photo_id
    product["cutout_id"] = job["result"]["cutout_asset_id"]
    product["mask_id"] = job["result"]["mask_asset_id"]
    return product


def test_cutout_keeps_original_pixels_and_links_assets(client: TestClient, product: dict[str, Any]) -> None:
    cutout = _image(client, product["cutout_id"])
    assert cutout.mode == "RGBA"
    x0, y0, x1, y1 = PRODUCT_BOX
    original = Image.open(io.BytesIO(_photo_png())).crop((x0, y0, x1 + 1, y1 + 1))
    assert cutout.convert("RGB").tobytes() == original.tobytes()
    assert cutout.getchannel("A").getextrema() == (255, 255)  # interior white label is kept

    links = {
        (a["asset"]["id"], a["role"]) for a in client.get(f"/api/products/{product['id']}").json()["assets"]
    }
    assert {(product["photo_id"], "product_photo"), (product["cutout_id"], "cutout")} <= links
    assert (product["mask_id"], "mask") in links
    meta = client.get(f"/api/assets/{product['cutout_id']}").json()
    assert meta["ai_generated"] is False and meta["source"] == "derived"
    assert meta["metadata"]["segmentation_model"] == "color_key"


def _scene(client: TestClient, product: dict[str, Any], **body: Any) -> dict[str, Any]:
    payload = {"cutout_asset_id": product["cutout_id"], "scene": "marble bathroom counter", "width": 512,
               "height": 512, "steps": 2, **body}  # fmt: skip
    job = _run(client, client.post(f"/api/products/{product['id']}/scene", json=payload))
    assert job["status"] == "completed", job
    generation: dict[str, Any] = client.get(f"/api/generations/{job['result']['generation_id']}").json()
    return generation


def test_scene_composites_exact_product_pixels(client: TestClient, product: dict[str, Any]) -> None:
    generation = _scene(client, product, placement={"x": 0.5, "y": 0.9, "native_scale": True}, num_images=2)
    assert generation["kind"] == "product_scene" and generation["product_id"] == product["id"]
    reports = generation["params"]["preservation"]
    assert len(reports) == 2 and all(r["exact"] and not r["resampled"] for r in reports)
    cutout = _image(client, product["cutout_id"]).convert("RGB")
    for asset in generation["assets"]:
        out = _image(client, asset["id"])
        box = tuple(asset["metadata"]["product_box"])
        assert out.crop(box).convert("RGB").tobytes() == cutout.tobytes()
        disclosure = json.loads(out.info["ai_disclosure"])
        assert disclosure["product_pixels"] == "original_photo"
        assert disclosure["background"] == "ai_generated"
    assert "empty uncluttered surface in the centre, in the lower part" in generation["params"]["prompt"]
    listed = client.get("/api/generations", params={"product_id": product["id"]}).json()["items"]
    assert [g["id"] for g in listed] == [generation["id"]]


def test_scene_with_harmonised_edges_and_watermark(client: TestClient, product: dict[str, Any]) -> None:
    generation = _scene(
        client, product, placement={"x": 0.95, "y": 1.0, "height_ratio": 0.6},
        harmonize={"enabled": True, "ring_px": 4, "strength": 0.3}, watermark=True,
    )  # fmt: skip
    report = generation["params"]["preservation"][0]
    assert report["exact"] and report["upscaled"] and report["clamped_to_frame"]
    assert report["protected_pixels"] < report["opaque_product_pixels"]  # the ring may be repainted
    assert report["watermark"] is True  # placed away from the product (bottom-right is taken)


def test_scene_on_user_background_needs_no_model(client: TestClient, product: dict[str, Any]) -> None:
    background_id = _upload(client, _png(Image.new("RGB", (800, 600), (120, 90, 60))), "bg.png")
    generation = _scene(
        client, product, background_asset_id=background_id, placement={"height_ratio": 0.5}, shadow=False
    )
    assert generation["model_key"] == "compositor"
    asset = generation["assets"][0]
    assert asset["ai_generated"] is False
    assert asset["metadata"]["generated_with_ai"] is False
    assert asset["metadata"]["background"] == "user_photo"
    out = _image(client, asset["id"]).convert("RGB")
    assert out.getpixel((5, 5)) == (120, 90, 60)


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"placement": {"height_ratio": 1.0}, "width": 256, "height": 1024}, "INVALID_GENERATION_REQUEST"),
        ({"width": 500}, "VALIDATION_ERROR"),
        ({"scene": "a schoolgirl holding it"}, "VALIDATION_ERROR"),
        ({"background_asset_id": "AST_X", "num_images": 2}, "VALIDATION_ERROR"),
        ({"cutout_asset_id": "__photo__"}, "INVALID_GENERATION_REQUEST"),
    ],
)
def test_scene_validation(
    client: TestClient, product: dict[str, Any], body: dict[str, Any], code: str
) -> None:
    if body.get("cutout_asset_id") == "__photo__":
        body = {**body, "cutout_asset_id": product["photo_id"]}  # linked, but not as a cutout
    payload = {"cutout_asset_id": product["cutout_id"], "scene": "desk", "width": 512, "height": 512, **body}
    response = client.post(f"/api/products/{product['id']}/scene", json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code


def test_cutout_with_user_mask_and_missing_model(client: TestClient) -> None:
    product = client.post("/api/products", json={"name": "Mug"}).json()
    photo_id = _upload(client, _photo_png())
    missing = client.post(
        f"/api/products/{product['id']}/cutout",
        json={"source_asset_id": photo_id, "model_key": "birefnet_general"},
    )
    # rembg is not installed in CI (NOT_INSTALLED) or the weights are absent (MODEL_MISSING).
    assert missing.status_code == 503, missing.text
    assert missing.json()["error"]["code"] in {"MODEL_MISSING", "PROVIDER_UNAVAILABLE"}

    mask = Image.new("L", (400, 300), 0)
    ImageDraw.Draw(mask).rectangle((10, 10, 59, 39), fill=255)
    mask_id = _upload(client, _png(mask), "mask.png")
    job = _run(
        client,
        client.post(
            f"/api/products/{product['id']}/cutout",
            json={"source_asset_id": photo_id, "mask_asset_id": mask_id},
        ),
    )
    assert job["status"] == "completed", job
    assert (job["result"]["width"], job["result"]["height"]) == (50, 30)
    assert job["result"]["segmentation_model"] == "user_mask"
