from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import REPO_ROOT, AppEnv, Settings


def test_relative_paths_are_anchored_at_repo_root() -> None:
    s = Settings(_env_file=None, data_dir=Path("data"), models_dir=Path("models"))
    assert s.data_dir == (REPO_ROOT / "data").resolve()
    assert s.models_config_path == (REPO_ROOT / "backend/config/models.yaml").resolve()


def test_default_database_url_lives_in_data_dir(tmp_path: Path) -> None:
    s = Settings(_env_file=None, data_dir=tmp_path)
    assert s.database_url == f"sqlite:///{(tmp_path / 'studio.db').as_posix()}"


def test_cors_origins_accepts_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert Settings(_env_file=None).cors_origins == ["http://a.test", "http://b.test"]


def test_empty_optional_paths_become_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FFMPEG_PATH", "")
    assert Settings(_env_file=None).ffmpeg_path is None


def test_fake_providers_forbidden_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env=AppEnv.PRODUCTION, enable_fake_providers=True)


def test_telemetry_is_always_off() -> None:
    assert Settings(_env_file=None).telemetry_enabled is False


def test_env_example_loads_with_defaults() -> None:
    s = Settings(_env_file=REPO_ROOT / ".env.example")
    assert s.app_env is AppEnv.DEVELOPMENT
    assert s.database_url is not None and s.database_url.startswith("sqlite:///")
    assert s.ffmpeg_path is None
    assert s.enable_fake_providers is False
