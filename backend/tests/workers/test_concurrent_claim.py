"""Two processes race to claim jobs from the same SQLite file: each job must be claimed exactly once."""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

from app.core.config import Settings
from app.db.session import create_db_engine, create_session_factory
from app.workers.queue import JobQueue

JOBS = 40


def _claim_all(database_url: str, worker_id: str, out: mp.Queue) -> None:  # type: ignore[type-arg]
    engine = create_db_engine(database_url)
    queue = JobQueue(create_session_factory(engine))
    claimed = []
    while (job := queue.claim_next(worker_id)) is not None:
        claimed.append(job.id)
    engine.dispose()
    out.put(claimed)


def test_no_double_claim_across_processes(settings: Settings, queue: JobQueue, tmp_path: Path) -> None:
    assert settings.database_url is not None
    expected = {queue.enqueue("a").id for _ in range(JOBS)}

    ctx = mp.get_context("spawn")
    out: mp.Queue = ctx.Queue()  # type: ignore[type-arg]
    procs = [ctx.Process(target=_claim_all, args=(settings.database_url, f"W{i}", out)) for i in range(3)]
    for p in procs:
        p.start()
    results = [out.get(timeout=60) for _ in procs]
    for p in procs:
        p.join(timeout=30)

    claimed = [job_id for batch in results for job_id in batch]
    assert len(claimed) == len(set(claimed)) == JOBS
    assert set(claimed) == expected
