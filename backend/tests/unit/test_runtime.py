from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config import DATA_SUBDIRS, Settings
from app.core.runtime import apply_process_env, ensure_data_dirs


def test_ensure_data_dirs_creates_layout(tmp_path: Path) -> None:
    s = Settings(_env_file=None, data_dir=tmp_path / "d", models_dir=tmp_path / "m")
    ensure_data_dirs(s)
    assert all((tmp_path / "d" / name).is_dir() for name in DATA_SUBDIRS)
    assert (tmp_path / "m").is_dir()


def test_offline_mode_sets_hf_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        monkeypatch.delenv(key, raising=False)
    apply_process_env(Settings(_env_file=None, offline_mode=True))
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
