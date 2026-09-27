"""Resolve a model the user picked (or the default) and insist it is ready before a job is queued."""

from __future__ import annotations

from app.core.errors import ModelMissingError, ProviderUnavailableError
from app.providers.base import ProviderKind, ProviderStatus
from app.providers.registry import ProviderInfo, ProviderRegistry


def require_available(registry: ProviderRegistry, kind: ProviderKind, key: str | None) -> ProviderInfo:
    info = registry.describe(registry.entry(kind, key))
    if info.status is ProviderStatus.MODEL_MISSING:
        raise ModelMissingError(info.detail)
    if info.status is not ProviderStatus.AVAILABLE:
        raise ProviderUnavailableError(info.detail or f"'{info.key}' is not available.")
    return info
