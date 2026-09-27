from __future__ import annotations

import shutil
from pathlib import Path

from app.core.errors import FfmpegMissingError


def resolve_binary(name: str, configured: Path | None) -> str | None:
    """Configured path wins (must exist); otherwise look on PATH."""
    if configured is not None:
        return str(configured) if configured.is_file() else None
    return shutil.which(name)


def require_binary(name: str, configured: Path | None) -> str:
    path = resolve_binary(name, configured)
    if path is None:
        env = f"{name.upper()}_PATH"
        raise FfmpegMissingError(f"{name} was not found. Install FFmpeg or set {env}.")
    return path
