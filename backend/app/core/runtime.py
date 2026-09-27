"""Process-level setup shared by the API and (later) the GPU worker."""

from __future__ import annotations

import os

from app.core.config import DATA_SUBDIRS, Settings

_OFFLINE_ENV = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")
_TELEMETRY_OPT_OUT = {"HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}


def ensure_data_dirs(settings: Settings) -> None:
    for name in DATA_SUBDIRS:
        settings.data_path(name).mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)


def apply_process_env(settings: Settings) -> None:
    """Must run before any Hugging Face library is imported for offline mode to take effect."""
    for key, value in _TELEMETRY_OPT_OUT.items():
        os.environ.setdefault(key, value)
    if settings.offline_mode:
        for key in _OFFLINE_ENV:
            os.environ[key] = "1"
    if settings.hf_home is not None:
        os.environ["HF_HOME"] = str(settings.hf_home)
