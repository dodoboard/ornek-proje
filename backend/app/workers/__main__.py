"""GPU worker entry point: `python -m app.workers` (run from backend/)."""

from __future__ import annotations

import argparse
import signal
import sys
from types import FrameType

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.runtime import apply_process_env, ensure_data_dirs
from app.db.migrations import wait_for_schema
from app.db.session import create_db_engine, create_session_factory
from app.workers.queue import JobQueue
from app.workers.registry import default_registry
from app.workers.runner import Worker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Influencer Studio worker")
    parser.add_argument("--once", action="store_true", help="process at most one job, then exit")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    apply_process_env(settings)
    ensure_data_dirs(settings)
    assert settings.database_url is not None
    # The API owns migrations; the worker only waits for the schema to be current.
    wait_for_schema(settings.database_url)

    engine = create_db_engine(settings.database_url)
    worker = Worker(settings, JobQueue(create_session_factory(engine)), default_registry())

    def _handle_signal(signum: int, _frame: FrameType | None) -> None:
        worker.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        if args.once:
            worker.start()
            try:
                worker.run_once()
            finally:
                worker.shutdown()
        else:
            worker.run_forever()
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
