"""End-to-end worker self-test: storage, disk, FFmpeg encode, GPU driver, Python ML packages.

This is a real job (no simulated work) that exercises progress, cancellation and subprocess control.
"""

from __future__ import annotations

import importlib.util
import shutil
from typing import Any

from app.core.config import get_settings
from app.services.ffmpeg.binary import resolve_binary
from app.services.ffmpeg.progress import FfmpegProgress
from app.services.system_info import detect_gpu
from app.workers.context import JobContext

JOB_TYPE = "diagnostics"
ENCODE_SECONDS = 4
MIN_FREE_GB = 20
ML_PACKAGES = ("torch", "diffusers", "transformers", "accelerate")


def _check_storage(ctx: JobContext) -> dict[str, Any]:
    probe = ctx.temp_dir / "write_test.bin"
    data = b"ai-influencer-studio" * 1024
    probe.write_bytes(data)
    ok = probe.read_bytes() == data
    probe.unlink()
    return {"status": "ok" if ok else "error"}


def _check_disk(ctx: JobContext) -> dict[str, Any]:
    free_gb = round(shutil.disk_usage(ctx.temp_dir).free / 1024**3, 1)
    return {"status": "ok" if free_gb >= MIN_FREE_GB else "warn", "free_gb": free_gb}


def _check_ffmpeg(ctx: JobContext, start: float, end: float) -> dict[str, Any]:
    settings = get_settings()
    ffmpeg = resolve_binary("ffmpeg", settings.ffmpeg_path)
    if ffmpeg is None:
        return {"status": "missing"}
    output = ctx.temp_dir / "encode_test.mp4"
    tracker = FfmpegProgress(ENCODE_SECONDS, ctx.stage_progress(start, end))
    args = [
        ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=duration={ENCODE_SECONDS}:size=640x360:rate=25",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-progress", "pipe:1", str(output),
    ]  # fmt: skip
    result = ctx.run_subprocess(args, timeout_s=120, on_stdout_line=tracker.feed)
    if result.returncode != 0 or not output.is_file():
        return {"status": "error", "detail": "H.264 test encode failed (libx264 missing?)"}
    return {"status": "ok", "encoder": "libx264", "bytes": output.stat().st_size}


def run_diagnostics(ctx: JobContext) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    ctx.report(5, stage="Checking storage")
    checks["storage"] = _check_storage(ctx)

    ctx.report(10, stage="Checking disk space")
    checks["disk"] = _check_disk(ctx)

    ctx.report(15, stage="Encoding FFmpeg test clip")
    checks["ffmpeg"] = _check_ffmpeg(ctx, 15, 85)

    ctx.report(88, stage="Querying GPU driver")
    gpu = detect_gpu()
    checks["gpu"] = {
        "status": gpu.status,
        "devices": [d.model_dump() for d in gpu.devices],
        "detail": gpu.detail,
    }

    ctx.report(95, stage="Checking ML packages")
    checks["python_packages"] = {
        name: "installed" if importlib.util.find_spec(name) else "missing" for name in ML_PACKAGES
    }
    return {"checks": checks}
