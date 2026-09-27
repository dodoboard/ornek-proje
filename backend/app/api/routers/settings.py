from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SessionDep, SettingsDep
from app.services.preferences import PreferencesRead, PreferencesUpdate, load_preferences, update_preferences

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=PreferencesRead)
def get_settings(session: SessionDep, settings: SettingsDep) -> PreferencesRead:
    return PreferencesRead(**load_preferences(session, settings).model_dump())


@router.patch("", response_model=PreferencesRead)
def patch_settings(patch: PreferencesUpdate, session: SessionDep, settings: SettingsDep) -> PreferencesRead:
    return PreferencesRead(**update_preferences(session, settings, patch).model_dump())
