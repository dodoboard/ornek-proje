from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import VramOutOfMemoryError


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


def test_request_id_is_propagated_when_safe(client: TestClient) -> None:
    assert client.get("/api/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    unsafe = client.get("/api/health", headers={"X-Request-ID": "bad id\n"}).headers["x-request-id"]
    assert unsafe != "bad id\n"


def test_system_reports_privacy_and_storage(client: TestClient) -> None:
    body = client.get("/api/system").json()
    assert body["privacy"] == {"telemetry_enabled": False, "offline_mode": False}
    assert body["storage"]["free_gb"] > 0
    assert body["gpu"]["status"] in {"ok", "missing", "error"}
    assert body["ffmpeg"]["status"] in {"ok", "missing", "error"}


def test_startup_creates_data_dirs(client: TestClient, settings) -> None:
    assert (settings.data_dir / "uploads").is_dir()


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}


def test_app_error_and_unhandled_error_envelopes(client: TestClient) -> None:
    router = APIRouter()

    @router.get("/api/_oom")
    def oom() -> None:
        raise VramOutOfMemoryError()

    @router.get("/api/_boom")
    def boom() -> None:
        raise RuntimeError("secret path /home/user/x")

    client.app.include_router(router)

    oom_response = client.get("/api/_oom")
    assert oom_response.status_code == 507
    assert oom_response.json()["error"]["code"] == "VRAM_OOM"

    boom_response = client.get("/api/_boom")
    assert boom_response.status_code == 500
    assert boom_response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}
    }
