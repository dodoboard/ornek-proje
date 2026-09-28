"""Host introspection that never initialises CUDA in the API process.

GPU data comes from `nvidia-smi` (driver-level query, no CUDA context, no VRAM allocated).
PyTorch-level details (arch list, bf16) are reported by the GPU worker in a later phase.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from app import __version__
from app.core.config import Settings
from app.schemas.system import (
    BinaryStatus,
    GpuInfo,
    GpuStatus,
    PrivacyStatus,
    StorageStatus,
    SystemResponse,
)

_TIMEOUT_S = 5.0
_NVIDIA_SMI_QUERY = "index,name,driver_version,memory.total,memory.used,memory.free"

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]
Which = Callable[[str], str | None]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False)  # noqa: S603


def parse_nvidia_smi(output: str) -> list[GpuInfo]:
    devices = []
    for line in output.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 6:
            continue
        index, name, driver, total, used, free = parts
        try:
            devices.append(
                GpuInfo(
                    index=int(index),
                    name=name,
                    driver_version=driver,
                    memory_total_mb=int(float(total)),
                    memory_used_mb=int(float(used)),
                    memory_free_mb=int(float(free)),
                )
            )
        except ValueError:
            continue
    return devices


def detect_gpu(which: Which = shutil.which, run: Runner = _run) -> GpuStatus:
    binary = which("nvidia-smi")
    if binary is None:
        return GpuStatus(status="missing", detail="nvidia-smi not found (no NVIDIA driver?)")
    try:
        result = run([binary, f"--query-gpu={_NVIDIA_SMI_QUERY}", "--format=csv,noheader,nounits"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GpuStatus(status="error", detail=f"nvidia-smi failed: {exc.__class__.__name__}")
    if result.returncode != 0:
        return GpuStatus(status="error", detail="nvidia-smi returned a non-zero exit code")
    devices = parse_nvidia_smi(result.stdout)
    if not devices:
        return GpuStatus(status="missing", detail="no NVIDIA GPU reported")
    return GpuStatus(status="ok", devices=devices)


def detect_binary(
    name: str, configured: Path | None, which: Which = shutil.which, run: Runner = _run
) -> BinaryStatus:
    path = str(configured) if configured is not None else which(name)
    if path is None or (configured is not None and not configured.is_file()):
        return BinaryStatus(status="missing", path=path)
    try:
        result = run([path, "-hide_banner", "-version"])
    except (OSError, subprocess.TimeoutExpired):
        return BinaryStatus(status="error", path=path)
    if result.returncode != 0:
        return BinaryStatus(status="error", path=path)
    first_line = result.stdout.splitlines()[0] if result.stdout else None
    return BinaryStatus(status="ok", path=path, version=first_line)


def storage_status(data_dir: Path) -> StorageStatus:
    usage = shutil.disk_usage(data_dir)
    gib = 1024**3
    return StorageStatus(
        data_dir=str(data_dir),
        total_gb=round(usage.total / gib, 1),
        used_gb=round(usage.used / gib, 1),
        free_gb=round(usage.free / gib, 1),
    )


def collect_system_info(settings: Settings) -> SystemResponse:
    return SystemResponse(
        app_name=settings.app_name,
        version=__version__,
        app_env=settings.app_env.value,
        python_version=platform.python_version(),
        platform=f"{platform.system()} {platform.release()} ({sys.platform})",
        device_preference=settings.device.value,
        performance_profile=settings.performance_profile.value,
        fake_providers_enabled=settings.enable_fake_providers,
        privacy=PrivacyStatus(
            telemetry_enabled=settings.telemetry_enabled, offline_mode=settings.offline_mode
        ),
        gpu=detect_gpu(),
        ffmpeg=detect_binary("ffmpeg", settings.ffmpeg_path),
        ffprobe=detect_binary("ffprobe", settings.ffprobe_path),
        storage=storage_status(settings.data_dir),
    )
