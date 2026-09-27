from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PIL import Image
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.asset import Asset
from app.models.enums import JobStatus
from app.models.generation import Generation
from app.models.job import Job
from app.providers.base import ProviderKind
from app.providers.device import DeviceInfo
from app.services.generated_media import DISCLOSURE_PNG_KEY
from app.services.preferences import PreferencesUpdate, update_preferences
from app.services.storage import StorageService
from app.workers.handlers.image_generate import JOB_TYPE, run_image_generate
from app.workers.queue import JobQueue
from app.workers.registry import HandlerRegistry
from app.workers.runner import Worker


@pytest.fixture
def dev_worker(
    settings: Settings, queue: JobQueue, session_factory: sessionmaker[Session]
) -> Iterator[Worker]:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with session_factory() as session:
        update_preferences(
            session, dev, PreferencesUpdate(default_models={ProviderKind.IMAGE: "dev_fake_image"})
        )
    registry = HandlerRegistry()
    registry.register(JOB_TYPE, run_image_generate)
    worker = Worker(dev, queue, registry, device=DeviceInfo(device="cpu", dtype="float32"))
    yield worker
    worker.shutdown()


def _job(factory: sessionmaker[Session], job_id: str) -> Job:
    with factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        return job


def _payload(**overrides: Any) -> dict[str, Any]:
    return {"prompt": "adult model on a marble terrace", "width": 256, "height": 320, "steps": 3,
            "seed": 42, "num_images": 2, **overrides}  # fmt: skip


def test_generates_assets_with_disclosure_and_provenance(
    dev_worker: Worker, queue: JobQueue, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    job = queue.enqueue(JOB_TYPE, _payload(watermark=True))
    dev_worker.run_once()
    stored = _job(session_factory, job.id)
    assert stored.status is JobStatus.COMPLETED, stored.error_message
    assert stored.result is not None
    assert stored.result["seeds"] == [42, 43]

    storage = StorageService(settings.data_dir)
    with session_factory() as session:
        generation = session.get(Generation, stored.result["generation_id"])
        assets = [session.get(Asset, i) for i in stored.result["asset_ids"]]
    assert generation is not None
    assert (generation.model_key, generation.provider, generation.job_id) == (
        "dev_fake_image",
        "dev_fake_image",
        job.id,
    )
    assert generation.params["steps"] == 3 and generation.device == {**generation.device, "device": "cpu"}

    for asset, seed in zip(assets, [42, 43], strict=True):
        assert asset is not None and asset.ai_generated and asset.source.value == "generated"
        assert (asset.width, asset.height, asset.mime) == (256, 320, "image/png")
        assert asset.metadata_json["seed"] == seed
        assert asset.metadata_json["dev_placeholder"] is True
        assert asset.metadata_json["generated_with_ai"] is False  # placeholder, not model output
        with Image.open(storage.resolve(asset.path)) as img:
            embedded = json.loads(img.text[DISCLOSURE_PNG_KEY])  # type: ignore[attr-defined]
        assert embedded["generation_id"] == generation.id and embedded["watermark"] is True
        assert storage.thumbnail_path(asset.id).is_file()


def test_same_seed_is_reproducible(
    dev_worker: Worker, queue: JobQueue, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    storage = StorageService(settings.data_dir)
    pixels = []
    for _ in range(2):
        job = queue.enqueue(JOB_TYPE, _payload(num_images=1, seed=7))
        dev_worker.run_once()
        result = _job(session_factory, job.id).result
        assert result is not None
        with session_factory() as session:
            asset = session.get(Asset, result["asset_ids"][0])
            assert asset is not None
        with Image.open(storage.resolve(asset.path)) as img:
            pixels.append(img.tobytes())  # file bytes differ (timestamps in metadata), pixels must not
    assert pixels[0] == pixels[1]


def test_random_seed_when_omitted(
    dev_worker: Worker, queue: JobQueue, session_factory: sessionmaker[Session]
) -> None:
    job = queue.enqueue(JOB_TYPE, _payload(seed=None, num_images=1))
    dev_worker.run_once()
    result = _job(session_factory, job.id).result
    assert result is not None and 0 <= result["seeds"][0] < 2**32


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"width": 250}, "INVALID_GENERATION_REQUEST"),
        ({"reference_asset_ids": ["AST_x"]}, "INVALID_GENERATION_REQUEST"),  # fake: 0 references
        ({"guidance_scale": 4.0}, "INVALID_GENERATION_REQUEST"),
        ({"project_id": "PRJ_missing"}, "NOT_FOUND"),
    ],
)
def test_invalid_requests_fail_cleanly(
    dev_worker: Worker,
    queue: JobQueue,
    session_factory: sessionmaker[Session],
    overrides: dict[str, Any],
    code: str,
) -> None:
    job = queue.enqueue(JOB_TYPE, _payload(**overrides))
    dev_worker.run_once()
    stored = _job(session_factory, job.id)
    assert stored.status is JobStatus.FAILED
    assert stored.error_code == code, stored.error_message


def test_cancel_during_generation_leaves_no_files(
    dev_worker: Worker, queue: JobQueue, session_factory: sessionmaker[Session], settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from app.providers.image import fake

    started = threading.Event()
    original: Callable[..., Any] = fake.render_placeholder

    def slow_render(*args: Any) -> Any:
        started.set()
        time.sleep(0.2)
        return original(*args)

    monkeypatch.setattr(fake, "render_placeholder", slow_render)
    job = queue.enqueue(JOB_TYPE, _payload(steps=20, num_images=4, width=512, height=512))

    def cancel_soon() -> None:
        queue.request_cancel(job.id)

    timer = threading.Timer(0.05, cancel_soon)
    timer.start()
    dev_worker.run_once()
    timer.join()
    assert _job(session_factory, job.id).status is JobStatus.CANCELLED
    assert not list((settings.data_dir / "outputs").rglob("*.png"))


def test_invalid_payload_reports_validation_error(
    dev_worker: Worker, queue: JobQueue, session_factory: sessionmaker[Session]
) -> None:
    job = queue.enqueue(JOB_TYPE, _payload(steps=10_000))
    dev_worker.run_once()
    assert _job(session_factory, job.id).error_code == "VALIDATION_ERROR"
