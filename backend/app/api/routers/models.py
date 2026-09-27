from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep, SettingsDep
from app.providers.base import ProviderKind
from app.providers.registry import ProviderInfo
from app.services.preferences import build_registry, load_preferences

router = APIRouter(prefix="/models", tags=["models"])


class KindModels(BaseModel):
    kind: ProviderKind
    default_key: str | None
    providers: list[ProviderInfo]


class ModelsResponse(BaseModel):
    fake_providers_enabled: bool
    kinds: list[KindModels]


@router.get("", response_model=ModelsResponse)
def list_models(session: SessionDep, settings: SettingsDep) -> ModelsResponse:
    """Configured models per kind with live status (installed? downloaded? implemented?)."""
    registry = build_registry(settings, load_preferences(session, settings))
    infos = registry.describe_all()
    kinds = [
        KindModels(
            kind=kind,
            default_key=registry.default_key(kind),
            providers=[i for i in infos if i.kind is kind],
        )
        for kind in ProviderKind
    ]
    return ModelsResponse(fake_providers_enabled=registry.fakes_enabled, kinds=kinds)
