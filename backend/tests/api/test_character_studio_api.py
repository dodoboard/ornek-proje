"""Demo A: create influencer → candidates → canonical → views → same character in another scene."""

from __future__ import annotations

from collections.abc import Iterator
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

PROFILE = {
    "name": "Deniz",
    "adult_age": 28,
    "presentation": "woman",
    "face_description": "oval face, light freckles",
    "hair": "shoulder-length wavy dark brown",
    "eye_color": "hazel",
    "style": "minimal chic",
    "clothing_preferences": "cream linen shirt",
}


@pytest.fixture
def dev_client(settings: Settings) -> Iterator[TestClient]:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with TestClient(create_app(dev), raise_server_exceptions=False) as client:
        client.patch("/api/settings", json={"default_models": {"image": "dev_fake_image"}})
        yield client


def _run(client: TestClient, job_id: str) -> dict[str, Any]:
    app: Any = client.app
    worker = Worker(
        app.state.settings, JobQueue(app.state.session_factory), default_registry(),
        device=DeviceInfo(device="cpu", dtype="float32"),
    )  # fmt: skip
    worker.run_once()
    worker.shutdown()
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "completed", job
    result: dict[str, Any] = job["result"]
    return result


def _generate(client: TestClient, character_id: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"/api/characters/{character_id}/generate", json=body)
    assert response.status_code == 202, response.text
    return _run(client, response.json()["id"])


def test_demo_a_full_flow(dev_client: TestClient) -> None:
    character = dev_client.post("/api/characters", json=PROFILE).json()
    cid = character["id"]

    bible = dev_client.get(f"/api/characters/{cid}/bible").json()
    assert bible["identity"].startswith("a 28-year-old woman, oval face, light freckles")
    assert bible["views"] == {"canonical": None, "front": None, "three_quarter": None, "full_body": None}

    # Views and scenes need a canonical portrait first.
    blocked = dev_client.post(f"/api/characters/{cid}/generate", json={"purpose": "front"})
    assert blocked.status_code == 409

    candidates = _generate(dev_client, cid, purpose="candidates", num_images=3, seed=100)
    assert candidates["seeds"] == [100, 101, 102]
    canonical_id = candidates["asset_ids"][1]
    updated = dev_client.put(f"/api/characters/{cid}/views/canonical", json={"asset_id": canonical_id})
    assert updated.status_code == 200

    preview = dev_client.post(f"/api/characters/{cid}/prompt-preview", json={"purpose": "full_body"}).json()
    assert preview["reference_asset_ids"] == [canonical_id]
    assert "cream linen shirt" in preview["prompt"]
    assert (preview["width"], preview["height"]) == (768, 1360)

    for role in ("front", "three_quarter", "full_body"):
        view = _generate(dev_client, cid, purpose=role, num_images=1)
        dev_client.put(f"/api/characters/{cid}/views/{role}", json={"asset_id": view["asset_ids"][0]})

    scene = _generate(
        dev_client, cid, purpose="scene", scene="sitting at a seaside café in Bodrum", num_images=1
    )
    generation = dev_client.get(f"/api/generations/{scene['generation_id']}").json()
    views = dev_client.get(f"/api/characters/{cid}/bible").json()["views"]
    # Scene is conditioned on canonical + all three views (fake provider accepts up to 4 references).
    assert generation["input_asset_ids"] == [
        views["canonical"],
        views["front"],
        views["three_quarter"],
        views["full_body"],
    ]
    assert generation["character_id"] == cid
    assert generation["params"]["purpose"] == "scene"
    assert "seaside café in Bodrum" in generation["params"]["prompt"]

    history = dev_client.get(f"/api/characters/{cid}/bible").json()["seed_history"]
    assert [h["purpose"] for h in history] == ["candidates"] * 3 + [
        "front",
        "three_quarter",
        "full_body",
        "scene",
    ]
    assert history[1]["asset_id"] == canonical_id and history[1]["seed"] == 101

    # Replacing a view keeps exactly one asset per role.
    dev_client.put(f"/api/characters/{cid}/views/canonical", json={"asset_id": candidates["asset_ids"][0]})
    roles = [a["role"] for a in dev_client.get(f"/api/characters/{cid}").json()["assets"]]
    assert roles.count("canonical") == 1


def test_uploaded_references_condition_candidates(dev_client: TestClient) -> None:
    cid = dev_client.post("/api/characters", json=PROFILE).json()["id"]
    ref = dev_client.post("/api/assets", files={"file": ("me.png", image_bytes(), "image/png")}).json()
    dev_client.post(f"/api/characters/{cid}/assets", json={"asset_id": ref["id"], "role": "reference"})
    result = _generate(dev_client, cid, purpose="candidates", num_images=1)
    generation = dev_client.get(f"/api/generations/{result['generation_id']}").json()
    assert generation["input_asset_ids"] == [ref["id"]]


def test_bible_update_changes_prompts(dev_client: TestClient) -> None:
    cid = dev_client.post("/api/characters", json=PROFILE).json()["id"]
    patched = dev_client.patch(
        f"/api/characters/{cid}/bible",
        json={"immutable_traits": ["small mole above left lip"], "prompt_template": "Shot on 35mm film."},
    ).json()
    assert patched["identity"].endswith("small mole above left lip")
    preview = dev_client.post(f"/api/characters/{cid}/prompt-preview", json={"purpose": "candidates"}).json()
    assert preview["prompt"].endswith("Shot on 35mm film.")
    assert (
        dev_client.patch(f"/api/characters/{cid}/bible", json={"immutable_traits": None}).status_code == 422
    )
    assert dev_client.patch(f"/api/characters/{cid}/bible", json={"seed_history": []}).status_code == 422


def test_scene_requires_text_and_adult_only(dev_client: TestClient) -> None:
    cid = dev_client.post("/api/characters", json=PROFILE).json()["id"]
    assert dev_client.post(f"/api/characters/{cid}/generate", json={"purpose": "scene"}).status_code == 422
    candidates = _generate(dev_client, cid, purpose="candidates", num_images=1)
    dev_client.put(f"/api/characters/{cid}/views/canonical", json={"asset_id": candidates["asset_ids"][0]})
    bad = dev_client.post(
        f"/api/characters/{cid}/generate", json={"purpose": "scene", "scene": "posing with a teenager"}
    )
    assert bad.status_code == 422


def test_view_rules(dev_client: TestClient) -> None:
    a = dev_client.post("/api/characters", json=PROFILE).json()["id"]
    b = dev_client.post("/api/characters", json={**PROFILE, "name": "Other"}).json()["id"]
    produced = _generate(dev_client, a, purpose="candidates", num_images=1)["asset_ids"][0]
    stolen = dev_client.put(f"/api/characters/{b}/views/canonical", json={"asset_id": produced})
    assert stolen.status_code == 409
    assert (
        dev_client.put(f"/api/characters/{a}/views/reference", json={"asset_id": produced}).status_code == 422
    )


def test_real_person_character_needs_consent_for_generation(dev_client: TestClient) -> None:
    consent = dev_client.post(
        "/api/consents",
        json={"subject_type": "face", "subject_name": "Jane", "granted_by": "me", "confirm": True},
    ).json()
    cid = dev_client.post(
        "/api/characters", json={**PROFILE, "is_real_person": True, "consent_id": consent["id"]}
    ).json()["id"]
    assert (
        dev_client.post(f"/api/characters/{cid}/generate", json={"purpose": "candidates"}).status_code == 202
    )
    dev_client.post(f"/api/consents/{consent['id']}/revoke")
    blocked = dev_client.post(f"/api/characters/{cid}/generate", json={"purpose": "candidates"})
    assert blocked.json()["error"]["code"] == "CONSENT_REQUIRED"
