"""Maps catalog entries (models.yaml) to provider implementations and reports their status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.core.config import AppEnv, Settings
from app.core.errors import NotFoundError, ProviderUnavailableError
from app.providers.base import Maturity, Provider, ProviderKind, ProviderStatus
from app.providers.catalog import ModelsConfig, ModelSpec, load_models_config

#: provider name (models.yaml `provider:`) → implementation. Unlisted names are "not implemented".
IMPLEMENTED: dict[str, type[Provider]] = {}

FAKE_KEYS: dict[ProviderKind, str] = {
    ProviderKind.IMAGE: "dev_fake_image",
    ProviderKind.VIDEO: "dev_fake_video",
    ProviderKind.LLM: "dev_fake_llm",
}

# Env overrides for the default model of each kind (spec §45).
ENV_PATH_OVERRIDES: dict[ProviderKind, str] = {
    ProviderKind.IMAGE: "flux_model_path",
    ProviderKind.VIDEO: "video_model_path",
    ProviderKind.LLM: "llm_model_path",
    ProviderKind.TTS: "tts_model_path",
    ProviderKind.LIPSYNC: "lipsync_model_path",
}


def register_provider(name: str, cls: type[Provider]) -> None:
    IMPLEMENTED[name] = cls


def _register_builtin() -> None:
    from app.providers.image.fake import FakeImageProvider
    from app.providers.image.flux2_diffusers import Flux2DiffusersProvider
    from app.providers.llm.fake import FakeLLMProvider
    from app.providers.llm.llamacpp_server import LlamaCppServerProvider
    from app.providers.llm.ollama import OllamaProvider
    from app.providers.segmentation.color_key import ColorKeySegmentationProvider
    from app.providers.segmentation.rembg_onnx import RembgSegmentationProvider
    from app.providers.video.fake import FakeVideoProvider

    IMPLEMENTED.setdefault("flux2_diffusers", Flux2DiffusersProvider)
    IMPLEMENTED.setdefault("ollama", OllamaProvider)
    IMPLEMENTED.setdefault("llamacpp_server", LlamaCppServerProvider)
    IMPLEMENTED.setdefault("dev_fake_llm", FakeLLMProvider)
    IMPLEMENTED.setdefault("rembg_onnx", RembgSegmentationProvider)
    IMPLEMENTED.setdefault("color_key", ColorKeySegmentationProvider)
    IMPLEMENTED.setdefault("dev_fake_image", FakeImageProvider)
    IMPLEMENTED.setdefault("dev_fake_video", FakeVideoProvider)


class ProviderInfo(BaseModel):
    kind: ProviderKind
    key: str
    provider: str
    status: ProviderStatus
    detail: str | None
    maturity: Maturity
    verification: str
    license_claim: str | None
    note: str | None
    source: str | None
    is_default: bool
    is_local: bool
    capabilities: dict[str, Any] | None


@dataclass(frozen=True)
class CatalogEntry:
    kind: ProviderKind
    key: str
    spec: ModelSpec


class ProviderRegistry:
    def __init__(
        self,
        settings: Settings,
        *,
        config: ModelsConfig | None = None,
        default_overrides: dict[str, str] | None = None,
        path_overrides: dict[str, str] | None = None,
    ) -> None:
        _register_builtin()
        self.settings = settings
        self.config = config or load_models_config(settings.models_config_path)
        self._default_overrides = default_overrides or {}
        self._path_overrides = path_overrides or {}
        self._instances: dict[tuple[ProviderKind, str], Provider] = {}

    @property
    def fakes_enabled(self) -> bool:
        return self.settings.enable_fake_providers and self.settings.app_env is not AppEnv.PRODUCTION

    # ------------------------------------------------------------------ catalog

    def entries(self, kind: ProviderKind | None = None) -> list[CatalogEntry]:
        result: list[CatalogEntry] = []
        for k in ProviderKind:
            if kind is not None and k is not kind:
                continue
            catalog = self.config.kinds.get(k)
            if catalog is not None:
                result.extend(
                    CatalogEntry(k, key, self._effective_spec(k, key, spec))
                    for key, spec in catalog.models.items()
                )
            if self.fakes_enabled and k in FAKE_KEYS:
                fake = FAKE_KEYS[k]
                result.append(CatalogEntry(k, fake, ModelSpec(provider=fake, verification="dev-only")))
        return result

    def _effective_spec(self, kind: ProviderKind, key: str, spec: ModelSpec) -> ModelSpec:
        path = self._path_overrides.get(key)
        if path is None and key == self._catalog_default(kind):
            env_attr = ENV_PATH_OVERRIDES.get(kind)
            env_value = getattr(self.settings, env_attr) if env_attr else None
            path = str(env_value) if env_value else None
        return spec.model_copy(update={"local_path": path}) if path else spec

    def _catalog_default(self, kind: ProviderKind) -> str | None:
        catalog = self.config.kinds.get(kind)
        return catalog.default if catalog else None

    def default_key(self, kind: ProviderKind) -> str | None:
        override = self._default_overrides.get(kind.value)
        keys = {e.key for e in self.entries(kind)}
        if override in keys:
            return override
        default = self._catalog_default(kind)
        return default if default in keys else None

    def entry(self, kind: ProviderKind, key: str | None = None) -> CatalogEntry:
        key = key or self.default_key(kind)
        for candidate in self.entries(kind):
            if candidate.key == key:
                return candidate
        raise NotFoundError(f"No {kind.value} model named '{key}'.")

    # ------------------------------------------------------------------ status

    def describe(self, entry: CatalogEntry) -> ProviderInfo:
        cls = IMPLEMENTED.get(entry.spec.provider)
        default = self.default_key(entry.kind) == entry.key
        source = entry.spec.local_path or entry.spec.repo_id
        common = {
            "kind": entry.kind,
            "key": entry.key,
            "provider": entry.spec.provider,
            "verification": entry.spec.verification,
            "license_claim": entry.spec.license_claim,
            "note": entry.spec.note,
            "source": source,
            "is_default": default,
        }
        if cls is None:
            return ProviderInfo(
                **common,
                status=ProviderStatus.NOT_IMPLEMENTED,
                detail="Integration not implemented yet.",
                maturity=Maturity.EXPERIMENTAL
                if entry.spec.verification == "experimental"
                else Maturity.STABLE,
                is_local=True,
                capabilities=None,
            )
        provider = self._instance(entry, cls)
        availability = provider.availability()
        maturity = cls.maturity
        if maturity is Maturity.STABLE and entry.spec.verification == "experimental":
            maturity = Maturity.EXPERIMENTAL
        return ProviderInfo(
            **common,
            status=availability.status,
            detail=availability.detail,
            maturity=maturity,
            is_local=cls.is_local,
            capabilities=provider.capabilities().model_dump(mode="json"),
        )

    def describe_all(self) -> list[ProviderInfo]:
        return [self.describe(e) for e in self.entries()]

    # ------------------------------------------------------------------ instances

    def _instance(self, entry: CatalogEntry, cls: type[Provider]) -> Provider:
        cache_key = (entry.kind, entry.key)
        existing = self._instances.get(cache_key)
        if existing is None or existing.spec != entry.spec:
            existing = cls(entry.key, entry.spec, self.settings)
            self._instances[cache_key] = existing
        return existing

    def get(self, kind: ProviderKind, key: str | None = None) -> Provider:
        """Return a usable provider instance or raise a user-facing error explaining why not."""
        entry = self.entry(kind, key)
        cls = IMPLEMENTED.get(entry.spec.provider)
        if cls is None:
            raise ProviderUnavailableError(f"'{entry.key}' is not implemented yet.")
        provider = self._instance(entry, cls)
        availability = provider.availability()
        if availability.status is not ProviderStatus.AVAILABLE:
            from app.core.errors import ModelMissingError

            if availability.status is ProviderStatus.MODEL_MISSING:
                raise ModelMissingError(availability.detail)
            raise ProviderUnavailableError(availability.detail)
        return provider
