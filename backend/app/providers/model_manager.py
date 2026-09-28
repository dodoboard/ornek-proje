"""Central model lifecycle: one heavy model on the GPU at a time, explicit unload + memory cleanup."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

from app.core.config import PerformanceProfile
from app.core.errors import ProviderUnavailableError
from app.providers.base import Provider, ProviderKind
from app.providers.device import DeviceInfo
from app.providers.memory import free_memory, translate_gpu_errors
from app.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)

P = TypeVar("P", bound=Provider)


class ModelManager:
    def __init__(self, registry: ProviderRegistry, device: DeviceInfo, profile: PerformanceProfile) -> None:
        self.registry = registry
        self.device = device
        self.profile = profile
        self._loaded: dict[tuple[ProviderKind, str], Provider] = {}

    @property
    def loaded_keys(self) -> list[str]:
        return [key for (_, key) in self._loaded]

    @contextmanager
    def use(self, kind: ProviderKind, expected: type[P], key: str | None = None) -> Iterator[P]:
        """Load (if needed) and yield a provider; unloads afterwards in Low VRAM mode."""
        provider = self.registry.get(kind, key)
        if not isinstance(provider, expected):
            raise ProviderUnavailableError(f"'{provider.key}' is not a {kind.value} provider.")
        self._ensure_loaded(provider)
        try:
            with translate_gpu_errors():
                yield provider
        finally:
            if self.profile is PerformanceProfile.LOW_VRAM:
                self.unload(provider)

    def _ensure_loaded(self, provider: Provider) -> None:
        slot = (provider.kind, provider.key)
        if slot in self._loaded and provider.loaded:
            return
        if provider.heavy:
            for other in [p for p in self._loaded.values() if p.heavy and p is not provider]:
                self.unload(other)
        logger.info("model_loading", extra={"model": provider.key, "device": self.device.device})
        with translate_gpu_errors(loading=True):
            provider.load(self.device, self.profile)
        self._loaded[slot] = provider

    def unload(self, provider: Provider) -> None:
        self._loaded.pop((provider.kind, provider.key), None)
        try:
            provider.unload()
        finally:
            free_memory()
        logger.info("model_unloaded", extra={"model": provider.key})

    def unload_all(self) -> None:
        for provider in list(self._loaded.values()):
            self.unload(provider)
