"""Application settings loaded from environment variables and the repo-root `.env` file."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

DATA_SUBDIRS: tuple[str, ...] = (
    "uploads",
    "outputs",
    "projects",
    "characters",
    "products",
    "properties",
    "thumbnails",
    "temp",
)


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Device(StrEnum):
    AUTO = "auto"
    CUDA = "cuda"
    CPU = "cpu"


class PerformanceProfile(StrEnum):
    PERFORMANCE = "performance"
    BALANCED = "balanced"
    LOW_VRAM = "low_vram"


class LogFormat(StrEnum):
    JSON = "json"
    TEXT = "text"


def _resolve_repo_path(value: Path) -> Path:
    """Relative paths are anchored at the repo root so behaviour does not depend on the CWD."""
    path = value.expanduser()
    return (path if path.is_absolute() else REPO_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_name: str = "AI Influencer Studio"
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = ["http://127.0.0.1:3000", "http://localhost:3000"]

    data_dir: Path = Path("data")
    models_dir: Path = Path("models")
    models_config_path: Path = Path("backend/config/models.yaml")
    database_url: str | None = None

    device: Device = Device.AUTO
    performance_profile: PerformanceProfile = PerformanceProfile.BALANCED
    offline_mode: bool = False
    hf_home: Path | None = None

    flux_model_path: Path | None = None
    video_model_path: Path | None = None
    llm_model_path: Path | None = None
    tts_model_path: Path | None = None
    lipsync_model_path: Path | None = None

    ffmpeg_path: Path | None = None
    ffprobe_path: Path | None = None

    # Upload limits
    max_image_upload_mb: int = Field(default=25, ge=1)
    max_video_upload_mb: int = Field(default=1024, ge=1)
    max_audio_upload_mb: int = Field(default=100, ge=1)
    max_image_pixels: int = Field(default=40_000_000, ge=1)
    auto_migrate: bool = True

    # Fake providers produce placeholder output for UI/backend development without a GPU.
    enable_fake_providers: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("data_dir", "models_dir", "models_config_path")
    @classmethod
    def _anchor_path(cls, value: Path) -> Path:
        return _resolve_repo_path(value)

    @field_validator(
        "database_url",
        "hf_home",
        "flux_model_path",
        "video_model_path",
        "llm_model_path",
        "tts_model_path",
        "lipsync_model_path",
        "ffmpeg_path",
        "ffprobe_path",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _finalize(self) -> Self:
        if self.database_url is None:
            self.database_url = f"sqlite:///{(self.data_dir / 'studio.db').as_posix()}"
        if self.app_env is AppEnv.PRODUCTION and self.enable_fake_providers:
            raise ValueError("ENABLE_FAKE_PROVIDERS must be false when APP_ENV=production")
        return self

    @property
    def telemetry_enabled(self) -> bool:
        """Telemetry is not implemented and is never sent anywhere."""
        return False

    def data_path(self, *parts: str) -> Path:
        return self.data_dir.joinpath(*parts)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
