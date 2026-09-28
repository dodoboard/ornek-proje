"""Restart the worker if it crashes (e.g. a CUDA driver fault kills the process).

Usage: `python -m app.workers.supervisor`. A clean exit (code 0) or Ctrl+C stops supervision.
Jobs orphaned by a crash are marked WORKER_LOST by the next worker's stale-job recovery.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import threading
import time
from types import FrameType

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger("app.workers.supervisor")

INITIAL_BACKOFF_S = 2.0
MAX_BACKOFF_S = 30.0
HEALTHY_RUN_S = 60.0
CHILD_GRACE_S = 15.0


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    stopping = threading.Event()
    child: subprocess.Popen[bytes] | None = None

    def _stop(signum: int, _frame: FrameType | None) -> None:
        stopping.set()
        if child is not None and child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    backoff = INITIAL_BACKOFF_S
    while not stopping.is_set():
        started = time.monotonic()
        child = subprocess.Popen([sys.executable, "-m", "app.workers"])
        try:
            code = child.wait()
        except KeyboardInterrupt:
            stopping.set()
            code = child.wait(timeout=CHILD_GRACE_S)
        if stopping.is_set() or code == 0:
            break
        if time.monotonic() - started > HEALTHY_RUN_S:
            backoff = INITIAL_BACKOFF_S
        logger.error("worker_crashed", extra={"exit_code": code, "restart_in_s": backoff})
        stopping.wait(backoff)
        backoff = min(MAX_BACKOFF_S, backoff * 2)
    logger.info("supervisor_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
