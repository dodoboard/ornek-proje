"""UI-editable runtime preferences stored in the `settings` table, layered over env Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import PerformanceProfile, Settings
from app.core.errors import AppError
from app.models.setting import AppSetting
from app.providers.base import ProviderKind
from app.providers.registry import ProviderRegistry

PREFERENCES_KEY = "preferences"
RESTART_REQUIRED_FIELDS = frozenset({"offline_mode"})


class InvalidPreferenceError(AppError):
    status_code = 422
    default_message = "Invalid setting."


class Preferences(BaseModel):
    model_config = ConfigDict(extra="ignore")

    performance_profile: PerformanceProfile = PerformanceProfile.BALANCED
    offline_mode: bool = False
    default_models: dict[ProviderKind, str] = Field(default_factory=dict)
    model_paths: dict[str, str] = Field(default_factory=dict)
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    ai_watermark: bool = False
    default_aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16"
    default_language: str = Field(default="tr", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performance_profile: PerformanceProfile | None = None
    offline_mode: bool | None = None
    default_models: dict[ProviderKind, str] | None = None
    model_paths: dict[str, str | None] | None = Field(
        default=None, description="Model key → local path. Null removes the override."
    )
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    ai_watermark: bool | None = None
    default_aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] | None = None
    default_language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")


class PreferencesRead(Preferences):
    telemetry_enabled: bool = False
    restart_required_fields: list[str] = sorted(RESTART_REQUIRED_FIELDS)


def _env_defaults(settings: Settings) -> Preferences:
    return Preferences(
        performance_profile=settings.performance_profile,
        offline_mode=settings.offline_mode,
        ffmpeg_path=str(settings.ffmpeg_path) if settings.ffmpeg_path else None,
        ffprobe_path=str(settings.ffprobe_path) if settings.ffprobe_path else None,
    )


def load_preferences(session: Session, settings: Settings) -> Preferences:
    row = session.get(AppSetting, PREFERENCES_KEY)
    base = _env_defaults(settings).model_dump()
    if row is not None and isinstance(row.value, dict):
        base.update(row.value)
    return Preferences.model_validate(base)


def effective_settings(settings: Settings, prefs: Preferences) -> Settings:
    return settings.model_copy(
        update={
            "performance_profile": prefs.performance_profile,
            "offline_mode": prefs.offline_mode,
            "ffmpeg_path": Path(prefs.ffmpeg_path) if prefs.ffmpeg_path else None,
            "ffprobe_path": Path(prefs.ffprobe_path) if prefs.ffprobe_path else None,
        }
    )


def build_registry(settings: Settings, prefs: Preferences) -> ProviderRegistry:
    return ProviderRegistry(
        effective_settings(settings, prefs),
        default_overrides={kind.value: key for kind, key in prefs.default_models.items()},
        path_overrides=dict(prefs.model_paths),
    )


def update_preferences(session: Session, settings: Settings, patch: PreferencesUpdate) -> Preferences:
    current = load_preferences(session, settings)
    data = current.model_dump()
    changes = patch.model_dump(exclude_unset=True)

    if "model_paths" in changes:
        paths = dict(current.model_paths)
        for key, value in (changes.pop("model_paths") or {}).items():
            if value is None or not str(value).strip():
                paths.pop(key, None)
            else:
                paths[key] = str(value).strip()
        data["model_paths"] = paths
    if "default_models" in changes:
        merged = dict(current.default_models)
        merged.update(changes.pop("default_models") or {})
        data["default_models"] = merged
    for key in ("ffmpeg_path", "ffprobe_path"):
        if key in changes:
            value = changes.pop(key)
            data[key] = (str(value).strip() or None) if value is not None else None
    data.update({k: v for k, v in changes.items() if v is not None})
    updated = Preferences.model_validate(data)

    registry = build_registry(settings, updated)
    for kind, key in updated.default_models.items():
        if key not in {e.key for e in registry.entries(kind)}:
            raise InvalidPreferenceError(f"Unknown {kind.value} model '{key}'.")
    known_keys = {e.key for e in registry.entries()}
    unknown = sorted(set(updated.model_paths) - known_keys)
    if unknown:
        raise InvalidPreferenceError(f"Unknown model key(s): {', '.join(unknown)}.")
    for key in ("ffmpeg_path", "ffprobe_path"):
        value = getattr(updated, key)
        if value is not None and not Path(value).is_file():
            raise InvalidPreferenceError(f"{key}: file not found.")

    row = session.get(AppSetting, PREFERENCES_KEY)
    payload = updated.model_dump(mode="json")
    if row is None:
        session.add(AppSetting(key=PREFERENCES_KEY, value=payload))
    else:
        row.value = payload
    session.commit()
    return updated
