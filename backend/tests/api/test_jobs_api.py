from __future__ import annotations

import json
import threading
import time
from typing import Any

from fastapi.testclient import TestClient

from app.models.enums import JobStatus
from app.workers.context import JobContext
from app.workers.queue import JobQueue
from app.workers.registry import HandlerRegistry
from app.workers.runner import Worker


def _queue(client: TestClient) -> JobQueue:
    return JobQueue(client.app.state.session_factory)  # type: ignore[attr-defined]


def _events(client: TestClient, job_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        event = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event == "job":
                events.append(json.loads(line.split(":", 1)[1]))
    return events


def test_list_filter_and_get(client: TestClient) -> None:
    queue = _queue(client)
    a = queue.enqueue("diagnostics")
    b = queue.enqueue("other")
    queue.request_cancel(b.id)

    listing = client.get("/api/jobs").json()
    assert listing["total"] == 2
    assert [j["id"] for j in client.get("/api/jobs", params={"active": True}).json()["items"]] == [a.id]
    assert [j["id"] for j in client.get("/api/jobs", params={"status": "cancelled"}).json()["items"]] == [
        b.id
    ]
    assert client.get("/api/jobs", params={"type": "other"}).json()["total"] == 1
    assert client.get(f"/api/jobs/{a.id}").json()["status"] == "queued"
    assert client.get("/api/jobs/JOB_missing").status_code == 404


def test_cancel_endpoint(client: TestClient) -> None:
    job = _queue(client).enqueue("diagnostics")
    response = client.delete(f"/api/jobs/{job.id}")
    assert response.status_code == 202
    assert response.json()["status"] == "cancelled"
    again = client.delete(f"/api/jobs/{job.id}")
    assert again.status_code == 409


def test_sse_streams_until_terminal(client: TestClient, settings: Any) -> None:
    settings.sse_poll_interval_s = 0.05
    settings.job_progress_min_interval_s = 0
    registry = HandlerRegistry()
    gate = threading.Event()

    def handler(ctx: JobContext) -> dict[str, Any]:
        gate.wait(5)
        for pct in (25, 50, 75):
            ctx.report(pct, status=JobStatus.GENERATING_IMAGE, stage="Rendering")
            time.sleep(0.15)
        return {"ok": True}

    registry.register("steps", handler)
    queue = _queue(client)
    worker = Worker(settings, queue, registry)
    job = queue.enqueue("steps")

    runner = threading.Thread(target=worker.run_once)
    runner.start()
    threading.Timer(0.2, gate.set).start()
    events = _events(client, job.id)
    runner.join(10)

    statuses = [e["status"] for e in events]
    progresses = [e["progress"] for e in events]
    assert statuses[-1] == "completed"
    assert "generating_image" in statuses
    assert progresses == sorted(progresses)
    assert events[-1]["result"] == {"ok": True}


def test_sse_for_finished_job_sends_one_event(client: TestClient) -> None:
    queue = _queue(client)
    job = queue.enqueue("x")
    queue.request_cancel(job.id)
    events = _events(client, job.id)
    assert [e["status"] for e in events] == ["cancelled"]


def test_sse_unknown_job_404(client: TestClient) -> None:
    assert client.get("/api/jobs/JOB_missing/events").status_code == 404


def test_diagnostics_endpoint_and_worker_status(client: TestClient, settings: Any) -> None:
    assert client.get("/api/system").json()["worker"]["status"] == "offline"

    response = client.post("/api/system/diagnostics")
    assert response.status_code == 202
    assert response.json()["type"] == "diagnostics"

    worker = Worker(settings, _queue(client), HandlerRegistry())
    _queue(client).register_worker(worker.worker_id, "host", 123)
    status = client.get("/api/system").json()["worker"]
    assert status["status"] == "online"
    assert status["worker_id"] == worker.worker_id
