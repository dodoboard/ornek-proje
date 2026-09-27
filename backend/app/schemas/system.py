from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ComponentStatus = Literal["ok", "missing", "error", "unknown"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class GpuInfo(BaseModel):
    index: int
    name: str
    driver_version: str
    memory_total_mb: int
    memory_used_mb: int
    memory_free_mb: int


class GpuStatus(BaseModel):
    status: ComponentStatus
    source: Literal["nvidia-smi"] = "nvidia-smi"
    detail: str | None = None
    devices: list[GpuInfo] = []


class BinaryStatus(BaseModel):
    status: ComponentStatus
    path: str | None = None
    version: str | None = None


class StorageStatus(BaseModel):
    data_dir: str
    total_gb: float
    used_gb: float
    free_gb: float


class PrivacyStatus(BaseModel):
    telemetry_enabled: bool
    offline_mode: bool


class SystemResponse(BaseModel):
    app_name: str
    version: str
    app_env: str
    python_version: str
    platform: str
    device_preference: str
    performance_profile: str
    fake_providers_enabled: bool
    privacy: PrivacyStatus
    gpu: GpuStatus
    ffmpeg: BinaryStatus
    ffprobe: BinaryStatus
    storage: StorageStatus
