from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.device import DeviceInfo
from app.workers.queue import JobQueue
from app.workers.registry import default_registry
from app.workers.runner import Worker
from tests.conftest import image_bytes


@pytest.fixture
def dev_client(settings: Settings) -> Iterator[TestClient]:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with TestClient(create_app(dev), raise_server_exceptions=False) as client:
        client.patch("/api/settings", json={"default_models": {"image": "dev_fake_image"}})
        yield client


def _run_worker(client: TestClient) -> None:
    app: Any = client.app
    worker = Worker(
        app.state.settings, JobQueue(app.state.session_factory), default_registry(),
        device=DeviceInfo(device="cpu", dtype="float32"),
    )  # fmt: skip
    worker.run_once()
    worker.shutdown()


BODY = {"prompt": "adult presenter in a bright studio", "width": 256, "height": 256, "steps": 2, "seed": 5}


def test_generate_queue_run_and_list(dev_client: TestClient) -> None:
    response = dev_client.post("/api/generate/image", json=BODY)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["type"] == "image.generate" and job["status"] == "queued"

    _run_worker(dev_client)
    done = dev_client.get(f"/api/jobs/{job['id']}").json()
    assert done["status"] == "completed", done
    generation_id = done["result"]["generation_id"]

    listing = dev_client.get("/api/generations", params={"kind": "image"}).json()
    assert listing["total"] == 1
    generation = dev_client.get(f"/api/generations/{generation_id}").json()
    assert generation["model_key"] == "dev_fake_image"
    assert generation["seeds"] == [5]
    [asset] = generation["assets"]
    assert asset["ai_generated"] is True and asset["metadata"]["dev_placeholder"] is True

    thumb = dev_client.get(f"/api/assets/{asset['id']}/thumbnail")
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    full = dev_client.get(f"/api/assets/{asset['id']}/content")
    assert full.headers["content-type"] == "image/png"


def test_watermark_defaults_to_setting(dev_client: TestClient) -> None:
    dev_client.patch("/api/settings", json={"ai_watermark": True})
    job = dev_client.post("/api/generate/image", json=BODY).json()
    assert dev_client.get(f"/api/jobs/{job['id']}").json()["status"] == "queued"
    _run_worker(dev_client)
    result = dev_client.get(f"/api/jobs/{job['id']}").json()["result"]
    generation = dev_client.get(f"/api/generations/{result['generation_id']}").json()
    assert generation["params"]["watermark"] is True


@pytest.mark.parametrize(
    ("override", "status", "code"),
    [
        ({"width": 250}, 422, "INVALID_GENERATION_REQUEST"),
        ({"guidance_scale": 5}, 422, "INVALID_GENERATION_REQUEST"),
        ({"num_images": 9}, 422, "VALIDATION_ERROR"),
        ({"prompt": "a 16 year old girl"}, 422, "VALIDATION_ERROR"),
        ({"prompt": "   "}, 422, "VALIDATION_ERROR"),
        ({"project_id": "PRJ_missing"}, 404, "NOT_FOUND"),
        ({"model_key": "nope"}, 404, "NOT_FOUND"),
        ({"negative_prompt": "blurry"}, 422, "VALIDATION_ERROR"),  # not a FLUX.2 parameter
    ],
)
def test_rejected_before_queueing(
    dev_client: TestClient, override: dict[str, Any], status: int, code: str
) -> None:
    response = dev_client.post("/api/generate/image", json={**BODY, **override})
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert dev_client.get("/api/jobs").json()["total"] == 0


def test_unavailable_model_is_rejected_with_reason(client: TestClient) -> None:
    # Default FLUX.2 klein: implemented, but torch/diffusers are not installed in this environment.
    response = client.post("/api/generate/image", json={**BODY, "width": 512, "height": 512})
    assert response.status_code in (503,)
    assert response.json()["error"]["code"] in {"PROVIDER_UNAVAILABLE", "MODEL_MISSING"}
    assert client.get("/api/jobs").json()["total"] == 0


def test_real_person_character_requires_consent(dev_client: TestClient) -> None:
    consent = dev_client.post(
        "/api/consents",
        json={"subject_type": "face", "subject_name": "J", "granted_by": "me", "confirm": True},
    ).json()
    character = dev_client.post(
        "/api/characters",
        json={"name": "Real", "adult_age": 30, "is_real_person": True, "consent_id": consent["id"]},
    ).json()
    ok = dev_client.post("/api/generate/image", json={**BODY, "character_id": character["id"]})
    assert ok.status_code == 202
    dev_client.post(f"/api/consents/{consent['id']}/revoke")
    blocked = dev_client.post("/api/generate/image", json={**BODY, "character_id": character["id"]})
    assert blocked.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_thumbnail_for_uploaded_image_is_created_lazily(
    client: TestClient, upload: Callable[..., dict]
) -> None:
    asset = upload(image_bytes(size=(900, 600)))
    response = client.get(f"/api/assets/{asset['id']}/thumbnail")
    assert response.status_code == 200
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(response.content)) as thumb:
        assert max(thumb.size) == 512
