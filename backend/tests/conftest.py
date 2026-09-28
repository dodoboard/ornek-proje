from __future__ import annotations

import io
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import AppEnv, Settings
from app.db.migrations import upgrade_to_head
from app.main import create_app


@pytest.fixture(scope="session")
def migrated_db_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run Alembic once; each test gets a copy (keeps tests on the real migration path)."""
    path = tmp_path_factory.mktemp("db") / "template.db"
    upgrade_to_head(f"sqlite:///{path.as_posix()}")
    return path


@pytest.fixture
def settings(tmp_path: Path, migrated_db_template: Path) -> Settings:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "studio.db"
    shutil.copy(migrated_db_template, db_path)
    return Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        data_dir=data_dir,
        models_dir=tmp_path / "models",
        database_url=f"sqlite:///{db_path.as_posix()}",
        log_format="text",
        auto_migrate=False,
        max_image_upload_mb=2,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 48)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 90)).save(buffer, format=fmt)
    return buffer.getvalue()


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe not installed"
)


@pytest.fixture
def make_media(tmp_path: Path) -> Callable[[str], bytes]:
    def _make(kind: str) -> bytes:
        out = tmp_path / {"mp4": "clip.mp4", "wav": "tone.wav"}[kind]
        lavfi = "testsrc=size=160x90:rate=10:duration=1" if kind == "mp4" else "sine=frequency=440:duration=1"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", lavfi, str(out)], check=True, timeout=60
        )
        return out.read_bytes()

    return _make


@pytest.fixture
def upload(client: TestClient) -> Callable[..., dict[str, object]]:
    def _upload(content: bytes | None = None, filename: str = "photo.png") -> dict[str, object]:
        response = client.post(
            "/api/assets", files={"file": (filename, content or image_bytes(), "image/png")}
        )
        assert response.status_code == 201, response.text
        body: dict[str, object] = response.json()
        return body

    return _upload
