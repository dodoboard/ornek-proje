"""Worker loop: claim → run handler → record outcome. One job at a time (single GPU)."""

from __future__ import annotations

import errno
import logging
import os
import socket
import threading
from datetime import timedelta

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.ids import IdPrefix, new_id
from app.core.logging import job_id_var
from app.workers.context import JobCancelled, JobContext
from app.workers.queue import ClaimedJob, JobQueue
from app.workers.registry import HandlerRegistry

logger = logging.getLogger(__name__)

GENERIC_FAILURE = "The job failed. See the worker log for details."


class Worker:
    def __init__(self, settings: Settings, queue: JobQueue, registry: HandlerRegistry) -> None:
        self.settings = settings
        self.queue = queue
        self.registry = registry
        self.worker_id = new_id(IdPrefix.WORKER)
        self.stop_event = threading.Event()
        self._current_job: str | None = None
        self._heartbeat_thread: threading.Thread | None = None

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        self.queue.register_worker(self.worker_id, socket.gethostname(), os.getpid())
        recovered = self.queue.recover_stale(timedelta(seconds=self.settings.worker_stale_after_s))
        if recovered:
            logger.warning("recovered_stale_jobs", extra={"job_ids": recovered})
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="heartbeat", daemon=True)
        self._heartbeat_thread.start()
        logger.info("worker_started", extra={"worker_id": self.worker_id, "handlers": self.registry.types()})

    def stop(self) -> None:
        self.stop_event.set()

    def shutdown(self) -> None:
        self.stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=self.settings.worker_heartbeat_interval_s + 1)
        self.queue.stop_worker(self.worker_id)
        logger.info("worker_stopped", extra={"worker_id": self.worker_id})

    def run_forever(self) -> None:
        self.start()
        try:
            while not self.stop_event.is_set():
                if not self.run_once():
                    self.stop_event.wait(self.settings.worker_poll_interval_s)
        finally:
            self.shutdown()

    def _heartbeat_loop(self) -> None:
        interval = self.settings.worker_heartbeat_interval_s
        stale_after = timedelta(seconds=self.settings.worker_stale_after_s)
        while not self.stop_event.wait(interval):
            try:
                self.queue.worker_heartbeat(self.worker_id, self._current_job)
                self.queue.recover_stale(stale_after)
            except Exception:
                logger.exception("heartbeat_failed")

    # ------------------------------------------------------------------ jobs

    def run_once(self) -> bool:
        """Claim and run at most one job. Returns True if a job was processed."""
        claimed = self.queue.claim_next(self.worker_id)
        if claimed is None:
            return False
        self._run(claimed)
        return True

    def _run(self, job: ClaimedJob) -> None:
        token = job_id_var.set(job.id)
        self._current_job = job.id
        ctx = JobContext(
            job_id=job.id,
            job_type=job.type,
            payload=job.payload,
            project_id=job.project_id,
            queue=self.queue,
            temp_root=self.settings.data_path("temp", "jobs"),
            stop_event=self.stop_event,
            min_report_interval_s=self.settings.job_progress_min_interval_s,
        )
        logger.info("job_started", extra={"type": job.type})
        try:
            handler = self.registry.get(job.type)
            if handler is None:
                self.queue.fail(job.id, ErrorCode.VALIDATION_ERROR, f"Unknown job type '{job.type}'.")
                return
            ctx.check_cancelled()
            result = handler(ctx)
            ctx.refresh_cancel_flag()
            ctx.check_cancelled()
            self.queue.complete(job.id, result)
            logger.info("job_completed")
        except JobCancelled:
            self.queue.mark_cancelled(job.id)
            logger.info("job_cancelled")
        except AppError as exc:
            self.queue.fail(job.id, exc.code, exc.message)
            logger.warning("job_failed", extra={"code": exc.code.value})
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                self.queue.fail(job.id, ErrorCode.DISK_FULL, "Not enough disk space to complete the job.")
            else:
                self.queue.fail(job.id, ErrorCode.GENERATION_FAILED, GENERIC_FAILURE)
            logger.exception("job_failed")
        except Exception:
            self.queue.fail(job.id, ErrorCode.GENERATION_FAILED, GENERIC_FAILURE)
            logger.exception("job_failed")
        finally:
            ctx.cleanup()
            self._current_job = None
            job_id_var.reset(token)
