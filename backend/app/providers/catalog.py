"""Model catalog loaded from backend/config/models.yaml (the only place repo IDs live)."""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.providers.base import Availability, ProviderKind, ProviderStatus


class ModelSpec(BaseModel):
    """One configured model. Unknown YAML keys are kept in `model_extra` for the provider to read."""

    model_config = ConfigDict(extra="allow", frozen=True)

    provider: str
    repo_id: str | None = None
    local_path: str | None = None
    revision: str | None = None
    pipeline_class: str | None = None
    verification: str = "needs-user-machine"
    license_claim: str | None = None
    note: str | None = None

    def extra(self, key: str, default: Any = None) -> Any:
        return (self.model_extra or {}).get(key, default)


class KindCatalog(BaseModel):
    default: str
    models: dict[str, ModelSpec] = Field(default_factory=dict)


class ModelsConfig(BaseModel):
    kinds: dict[ProviderKind, KindCatalog]


def parse_models_config(raw: dict[str, Any]) -> ModelsConfig:
    kinds: dict[ProviderKind, KindCatalog] = {}
    for kind in ProviderKind:
        section = raw.get(kind.value)
        if isinstance(section, dict):
            models = {k: v for k, v in (section.get("models") or {}).items() if isinstance(v, dict)}
            kinds[kind] = KindCatalog(default=section.get("default", ""), models=models)
    return ModelsConfig(kinds=kinds)


@lru_cache(maxsize=4)
def load_models_config(path: Path) -> ModelsConfig:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a mapping")
    return parse_models_config(raw)


# --------------------------------------------------------------------------- availability helpers


def missing_packages(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if importlib.util.find_spec(name) is None]


def hf_hub_cache_dir(settings: Settings) -> Path:
    """Mirror huggingface_hub's cache resolution without importing it."""
    if cache := os.environ.get("HF_HUB_CACHE"):
        return Path(cache)
    hf_home = settings.hf_home or (Path(os.environ["HF_HOME"]) if os.environ.get("HF_HOME") else None)
    if hf_home is None:
        xdg = os.environ.get("XDG_CACHE_HOME")
        hf_home = (Path(xdg) if xdg else Path.home() / ".cache") / "huggingface"
    return Path(hf_home) / "hub"


def is_repo_cached(repo_id: str, settings: Settings) -> bool:
    snapshots = hf_hub_cache_dir(settings) / f"models--{repo_id.replace('/', '--')}" / "snapshots"
    return snapshots.is_dir() and any(p.is_dir() and any(p.iterdir()) for p in snapshots.iterdir())


def resolve_local_path(value: str | None, settings: Settings) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else settings.models_dir / path


def weights_status(spec: ModelSpec, settings: Settings) -> Availability:
    local = resolve_local_path(spec.local_path, settings)
    if local is not None:
        if local.exists():
            return Availability(ProviderStatus.AVAILABLE)
        return Availability(ProviderStatus.MODEL_MISSING, f"Local model path not found: {local}")
    if spec.repo_id is None:
        return Availability(ProviderStatus.AVAILABLE)
    if is_repo_cached(spec.repo_id, settings):
        return Availability(ProviderStatus.AVAILABLE)
    if settings.offline_mode:
        return Availability(ProviderStatus.MODEL_MISSING, f"{spec.repo_id} is not downloaded (offline mode).")
    return Availability(
        ProviderStatus.MODEL_MISSING,
        f"{spec.repo_id} is not downloaded yet. Run backend/scripts/download_models.py or set a local path.",
    )
