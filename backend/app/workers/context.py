"""Per-job context for handlers: progress reporting, cooperative cancellation, temp dir, subprocesses."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.enums import JobStatus
from app.providers.base import GenerationContext
from app.workers.queue import JobQueue

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from app.providers.model_manager import ModelManager

logger = logging.getLogger(__name__)

SUBPROCESS_POLL_S = 0.2
TERMINATE_GRACE_S = 5.0


class JobCancelled(Exception):
    """Raised inside a handler when the user (or shutdown) cancels the job."""


class WorkerStopping(AppError):
    code = ErrorCode.WORKER_STOPPED
    status_code = 503
    default_message = "The worker was stopped while this job was running. Please retry."


class JobContext:
    def __init__(
        self,
        *,
        job_id: str,
        job_type: str,
        payload: dict[str, Any],
        project_id: str | None,
        queue: JobQueue,
        temp_root: Path,
        stop_event: threading.Event,
        min_report_interval_s: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
        settings: Settings | None = None,
        models: ModelManager | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings
        self._models = models
        self._session_factory = session_factory
        self.job_id = job_id
        self.job_type = job_type
        self.payload = payload
        self.project_id = project_id
        self._queue = queue
        self._stop_event = stop_event
        self._min_interval = min_report_interval_s
        self._clock = clock
        self._last_report = float("-inf")
        self._cancelled = False
        self._status = JobStatus.RUNNING
        self.temp_dir = temp_root / job_id
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ progress

    def report(
        self,
        progress: float | None = None,
        *,
        status: JobStatus | None = None,
        stage: str | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> None:
        """Throttled progress update. Status/stage changes are always written. Raises JobCancelled."""
        changed = (status is not None and status is not self._status) or stage is not None
        now = self._clock()
        if force or changed or now - self._last_report >= self._min_interval:
            if status is not None:
                self._status = status
            self._cancelled = self._queue.report(
                self.job_id,
                status=status,
                progress=None if progress is None else round(progress),
                stage=stage,
                message=message,
            )
            self._last_report = now
        self.check_cancelled()

    def stage_progress(self, start: float, end: float) -> Callable[[float], None]:
        """Map a sub-task's 0..1 fraction onto the [start, end] slice of overall progress."""

        def _update(fraction: float) -> None:
            clamped = min(1.0, max(0.0, fraction))
            self.report(start + (end - start) * clamped)

        return _update

    def generation_context(self, start: float, end: float) -> GenerationContext:
        """Context for a provider call whose progress maps onto [start, end] of the job."""
        return GenerationContext(
            temp_dir=self.temp_dir,
            progress=self.stage_progress(start, end),
            run_subprocess=self.run_subprocess,
        )

    def session(self) -> Session:
        """New DB session for handler use (`with ctx.session() as s:`)."""
        if self._session_factory is None:
            raise RuntimeError("This job context has no database access.")
        return self._session_factory()

    @property
    def models(self) -> ModelManager:
        if self._models is None:
            raise RuntimeError("This job context has no model manager.")
        return self._models

    # ------------------------------------------------------------------ cancellation

    @property
    def cancel_requested(self) -> bool:
        return self._cancelled or self._stop_event.is_set()

    def check_cancelled(self) -> None:
        if self._stop_event.is_set():
            raise WorkerStopping()
        if self._cancelled:
            raise JobCancelled()

    def refresh_cancel_flag(self) -> None:
        self._cancelled = self._cancelled or self._queue.is_cancel_requested(self.job_id)

    # ------------------------------------------------------------------ subprocesses

    def run_subprocess(
        self,
        args: list[str],
        *,
        timeout_s: float | None = None,
        on_stdout_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run argv (never a shell string); terminates the process on cancel/timeout."""
        if not args or not isinstance(args, list):
            raise ValueError("args must be a non-empty argv list")
        stdout_lines: list[str] = []
        stderr_chunks: list[str] = []
        proc = subprocess.Popen(  # noqa: S603 — argv list, shell=False
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
        )

        def _pump_stdout() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                stdout_lines.append(line)
                if on_stdout_line is not None:
                    try:
                        on_stdout_line(line.rstrip("\n"))
                    except Exception:
                        logger.exception("stdout_callback_failed")

        def _pump_stderr() -> None:
            assert proc.stderr is not None
            stderr_chunks.append(proc.stderr.read())

        readers = [threading.Thread(target=f, daemon=True) for f in (_pump_stdout, _pump_stderr)]
        for reader in readers:
            reader.start()

        started = self._clock()
        try:
            while proc.poll() is None:
                self.refresh_cancel_flag()
                if self.cancel_requested:
                    _terminate(proc)
                    self.check_cancelled()
                if timeout_s is not None and self._clock() - started > timeout_s:
                    _terminate(proc)
                    raise subprocess.TimeoutExpired(args, timeout_s)
                time.sleep(SUBPROCESS_POLL_S)
        finally:
            if proc.poll() is None:
                _terminate(proc)
            for reader in readers:
                reader.join(timeout=TERMINATE_GRACE_S)
        return subprocess.CompletedProcess(
            args, proc.returncode, "".join(stdout_lines), "".join(stderr_chunks)
        )

    # ------------------------------------------------------------------ cleanup

    def cleanup(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def _terminate(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=TERMINATE_GRACE_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
