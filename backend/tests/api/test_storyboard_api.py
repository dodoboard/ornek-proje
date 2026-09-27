"""Script generation (template + dev LLM) and storyboard editing through API + worker."""

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


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with TestClient(create_app(dev), raise_server_exceptions=False) as c:
        yield c


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
    assert job["status"] == "completed", job
    return job


@pytest.fixture
def project(client: TestClient) -> dict[str, Any]:
    product = client.post(
        "/api/products",
        json={
            "name": "Aurora Serum",
            "price": "1299",
            "currency": "TRY",
            "features": ["Hyaluronik asit içerir"],
        },
    ).json()
    project: dict[str, Any] = client.post(
        "/api/projects",
        json={"type": "product_ad", "name": "Serum launch", "product_id": product["id"],
              "settings": {"duration_s": 15, "language": "tr", "aspect_ratio": "9:16"}},
    ).json()  # fmt: skip
    return project


def test_template_script_uses_verified_facts(client: TestClient, project: dict[str, Any]) -> None:
    job = _run(client, client.post(f"/api/projects/{project['id']}/script", json={"template_only": True}))
    assert job["result"]["source"] == "template" and job["result"]["version"] == 1

    board = client.get(f"/api/projects/{project['id']}/storyboard").json()
    assert board["aspect_ratio"] == "9:16" and board["total_duration_s"] == 15
    texts = [s["on_screen_text"] for s in board["shots"]]
    assert "Aurora Serum" in texts and "1.299 TRY" in texts and "Hyaluronik asit içerir" in texts
    closeup = next(s for s in board["shots"] if s["type"] == "product_closeup")
    assert (
        closeup["generation_method"] == "product_composite" and closeup["disclosure_label"] == "ai_enhanced"
    )

    [script] = client.get(f"/api/projects/{project['id']}/scripts").json()
    assert script["source"] == "template"
    assert "{{product.price}}" in str(script["attempts"]) or script["attempts"] == []
    assert "product.price" in script["fact_report"]["placeholders"]


def test_dev_llm_script_and_new_version(client: TestClient, project: dict[str, Any]) -> None:
    _run(client, client.post(f"/api/projects/{project['id']}/script", json={"template_only": True}))
    job = _run(
        client,
        client.post(
            f"/api/projects/{project['id']}/script", json={"llm_model_key": "dev_fake_llm", "brief": "kısa"}
        ),
    )
    assert job["result"]["source"] == "llm" and job["result"]["version"] == 2
    board = client.get(f"/api/projects/{project['id']}/storyboard").json()
    assert board["version"] == 2 and board["id"] == job["result"]["storyboard_id"]
    scripts = client.get(f"/api/projects/{project['id']}/scripts").json()
    assert [s["source"] for s in scripts] == ["llm", "template"]
    assert scripts[0]["llm_model"] == "dev_fake_llm" and scripts[0]["brief"] == "kısa"


def test_unavailable_llm_is_rejected_before_queueing(client: TestClient, project: dict[str, Any]) -> None:
    response = client.post(f"/api/projects/{project['id']}/script", json={"llm_model_key": "ollama_default"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] in {"PROVIDER_UNAVAILABLE", "MODEL_MISSING"}
    bad = client.post(f"/api/projects/{project['id']}/script", json={"brief": "a schoolgirl presenter"})
    assert bad.status_code == 422


def test_edit_add_reorder_delete_shots(client: TestClient, project: dict[str, Any]) -> None:
    _run(client, client.post(f"/api/projects/{project['id']}/script", json={"template_only": True}))
    board = client.get(f"/api/projects/{project['id']}/storyboard").json()
    first = board["shots"][0]

    patched = client.patch(
        f"/api/shots/{first['id']}", json={"dialogue": "Merhaba!", "generation_method": "real_footage"}
    ).json()
    assert patched["edited"] and patched["dialogue"] == "Merhaba!"
    assert patched["disclosure_label"] == "real_footage"

    added = client.post(f"/api/storyboards/{board['id']}/shots", json={"type": "text_card", "position": 0,
                                                                     "on_screen_text": "Yeni"})  # fmt: skip
    assert added.status_code == 201
    shots = added.json()["shots"]
    assert shots[0]["on_screen_text"] == "Yeni" and [s["position"] for s in shots] == list(range(len(shots)))

    order = [s["id"] for s in reversed(shots)]
    reordered = client.put(f"/api/storyboards/{board['id']}/order", json={"shot_ids": order}).json()
    assert [s["id"] for s in reordered["shots"]] == order
    assert (
        client.put(f"/api/storyboards/{board['id']}/order", json={"shot_ids": order[:-1]}).status_code == 409
    )

    assert client.delete(f"/api/shots/{order[0]}").status_code == 204
    after = client.get(f"/api/storyboards/{board['id']}").json()["shots"]
    assert [s["id"] for s in after] == order[1:] and [s["position"] for s in after] == list(range(len(after)))
    for shot in after[:-1]:
        client.delete(f"/api/shots/{shot['id']}")
    assert client.delete(f"/api/shots/{after[-1]['id']}").status_code == 409  # keep at least one shot
    assert client.get("/api/projects/PRJ_missing/storyboard").status_code == 404
