"""Job type → handler registry. Handlers return a JSON-serialisable result dict."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.workers.context import JobContext

JobHandler = Callable[[JobContext], dict[str, Any]]


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        if job_type in self._handlers:
            raise ValueError(f"handler already registered for {job_type!r}")
        self._handlers[job_type] = handler

    def get(self, job_type: str) -> JobHandler | None:
        return self._handlers.get(job_type)

    def types(self) -> list[str]:
        return sorted(self._handlers)


def default_registry() -> HandlerRegistry:
    from app.workers.handlers import (
        diagnostics,
        image_edit,
        image_generate,
        product,
        script_generate,
        video_generate,
    )

    registry = HandlerRegistry()
    registry.register(diagnostics.JOB_TYPE, diagnostics.run_diagnostics)
    registry.register(image_generate.JOB_TYPE, image_generate.run_image_generate)
    registry.register(image_edit.JOB_TYPE, image_edit.run_image_edit)
    registry.register(product.CUTOUT_JOB, product.run_product_cutout)
    registry.register(product.SCENE_JOB, product.run_product_scene)
    registry.register(script_generate.JOB_TYPE, script_generate.run_script_generate)
    registry.register(video_generate.JOB_TYPE, video_generate.run_video_generate)
    return registry
