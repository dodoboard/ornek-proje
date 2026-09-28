from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.job import Worker as WorkerRow
from app.providers.base import ImageGenerationProvider, ImageRequest, ProviderKind
from app.providers.device import DeviceInfo
from app.services.preferences import PreferencesUpdate, update_preferences
from app.workers.context import JobContext
from app.workers.queue import JobQueue
from app.workers.registry import HandlerRegistry
from app.workers.runner import Worker


def test_handler_uses_model_manager_with_dev_provider(
    settings: Settings, queue: JobQueue, session_factory: sessionmaker[Session]
) -> None:
    dev = settings.model_copy(update={"enable_fake_providers": True, "job_progress_min_interval_s": 0})
    with session_factory() as session:
        update_preferences(
            session, dev, PreferencesUpdate(default_models={ProviderKind.IMAGE: "dev_fake_image"})
        )

    def handler(ctx: JobContext) -> dict[str, Any]:
        with ctx.models.use(ProviderKind.IMAGE, ImageGenerationProvider) as provider:
            images = provider.generate(
                ImageRequest(prompt="test", width=64, height=64, steps=2, seed=1),
                ctx.generation_context(10, 90),
            )
        return {"provider": provider.key, "size": list(images[0].size)}

    registry = HandlerRegistry()
    registry.register("img", handler)
    worker = Worker(dev, queue, registry, device=DeviceInfo(device="cpu", dtype="float32"))
    worker.start()
    try:
        job = queue.enqueue("img")
        worker.run_once()
    finally:
        worker.shutdown()

    with session_factory() as session:
        stored = session.get(Job, job.id)
        row = session.get(WorkerRow, worker.worker_id)
    assert stored is not None and stored.status is JobStatus.COMPLETED, stored and stored.error_message
    assert stored.result == {"provider": "dev_fake_image", "size": [64, 64]}
    assert row is not None and row.runtime is not None and row.runtime["device"] == "cpu"


def test_unimplemented_default_fails_with_clear_code(
    settings: Settings, queue: JobQueue, session_factory: sessionmaker[Session]
) -> None:
    def handler(ctx: JobContext) -> dict[str, Any]:
        with ctx.models.use(ProviderKind.IMAGE, ImageGenerationProvider):
            return {}

    registry = HandlerRegistry()
    registry.register("img", handler)
    worker = Worker(settings, queue, registry, device=DeviceInfo(device="cpu", dtype="float32"))
    job = queue.enqueue("img")
    worker.run_once()
    with session_factory() as session:
        stored = session.get(Job, job.id)
    assert stored is not None
    assert (stored.status, stored.error_code) == (JobStatus.FAILED, "PROVIDER_UNAVAILABLE")
