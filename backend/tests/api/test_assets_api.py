from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from tests.conftest import image_bytes, requires_ffmpeg


def _post(client: TestClient, content: bytes, filename: str) -> tuple[int, dict]:
    response = client.post("/api/assets", files={"file": (filename, content, "application/octet-stream")})
    return response.status_code, response.json()


def test_upload_png_stores_safe_file(client: TestClient, settings: Settings) -> None:
    status, body = _post(client, image_bytes(), "../../etc/My Photo.PNG")
    assert status == 201
    assert body["id"].startswith("AST_")
    assert body["kind"] == "image"
    assert (body["width"], body["height"]) == (64, 48)
    assert body["original_filename"] == "My Photo.PNG"
    assert len(body["checksum_sha256"]) == 64

    stored = list((settings.data_dir / "uploads" / "image").rglob("*.png"))
    assert [p.name for p in stored] == [f"{body['id']}.png"]


@pytest.mark.parametrize(("fmt", "name"), [("JPEG", "a.jpg"), ("JPEG", "a.jpeg"), ("WEBP", "a.webp")])
def test_upload_other_image_formats(client: TestClient, fmt: str, name: str) -> None:
    status, body = _post(client, image_bytes(fmt), name)
    assert status == 201, body


def test_content_endpoint_serves_file_with_nosniff(client: TestClient, upload: Callable[..., dict]) -> None:
    asset = upload()
    response = client.get(f"/api/assets/{asset['id']}/content")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == image_bytes()


@pytest.mark.parametrize(
    ("content", "filename", "code"),
    [
        (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "x.svg",
            "UNSUPPORTED_FORMAT",
        ),
        (b"GIF89a\x01\x00\x01\x00", "x.gif", "UNSUPPORTED_FORMAT"),
        (b"MZ\x90\x00 not an image", "x.png", "UNSUPPORTED_FORMAT"),
        (image_bytes(), "x.jpg", "UNSUPPORTED_FORMAT"),  # extension/content mismatch
        (image_bytes(), "x.png.exe", "UNSUPPORTED_FORMAT"),
        (image_bytes()[:40], "x.png", "FILE_INVALID"),  # truncated
        (b"", "x.png", "FILE_INVALID"),
    ],
)
def test_upload_rejections(
    client: TestClient, settings: Settings, content: bytes, filename: str, code: str
) -> None:
    status, body = _post(client, content, filename)
    assert status in (413, 415, 422)
    assert body["error"]["code"] == code
    assert not list((settings.data_dir / "uploads").rglob("*.*"))
    assert not list((settings.data_dir / "temp").iterdir())


def test_upload_too_large(client: TestClient, settings: Settings) -> None:
    big = image_bytes() + b"\0" * (3 * 1024 * 1024)
    status, body = _post(client, big, "x.png")
    assert status == 413
    assert body["error"]["code"] == "FILE_TOO_LARGE"


def test_decompression_bomb_rejected(client: TestClient, settings: Settings) -> None:
    settings.max_image_pixels = 100
    status, body = _post(client, image_bytes(size=(20, 20)), "x.png")
    assert status == 422
    assert body["error"]["code"] == "FILE_INVALID"


@requires_ffmpeg
def test_upload_video_and_audio(client: TestClient, make_media: Callable[[str], bytes]) -> None:
    status, video = _post(client, make_media("mp4"), "clip.mp4")
    assert status == 201, video
    assert video["kind"] == "video"
    assert (video["width"], video["height"]) == (160, 90)
    assert video["duration_s"] == pytest.approx(1.0, abs=0.2)

    status, audio = _post(client, make_media("wav"), "tone.wav")
    assert status == 201, audio
    assert audio["kind"] == "audio"


@requires_ffmpeg
def test_fake_video_with_valid_header_rejected(client: TestClient) -> None:
    fake = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 200
    status, body = _post(client, fake, "clip.mp4")
    assert status == 422
    assert body["error"]["code"] == "FILE_INVALID"


def test_video_without_ffprobe_reports_ffmpeg_missing(client: TestClient, settings: Settings) -> None:
    settings.ffprobe_path = Path("/nonexistent/ffprobe")
    fake = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 200
    status, body = _post(client, fake, "clip.mp4")
    assert status == 503
    assert body["error"]["code"] == "FFMPEG_MISSING"


def test_delete_asset_removes_file_and_blocks_when_in_use(
    client: TestClient, settings: Settings, upload: Callable[..., dict]
) -> None:
    asset = upload()
    product = client.post("/api/products", json={"name": "Perfume"}).json()
    client.post(
        f"/api/products/{product['id']}/assets", json={"asset_id": asset["id"], "role": "product_photo"}
    )

    assert client.delete(f"/api/assets/{asset['id']}").json()["error"]["code"] == "CONFLICT"

    client.delete(f"/api/products/{product['id']}/assets/{asset['id']}")
    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204
    assert client.get(f"/api/assets/{asset['id']}").status_code == 404
    assert not list((settings.data_dir / "uploads").rglob("*.png"))
