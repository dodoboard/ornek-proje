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
    from app.workers.handlers.diagnostics import JOB_TYPE, run_diagnostics

    registry = HandlerRegistry()
    registry.register(JOB_TYPE, run_diagnostics)
    return registry
