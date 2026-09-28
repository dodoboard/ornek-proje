from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProjectType
from app.schemas.common import LongText, Name, PatchModel, TimestampedRead

Platform = Literal["instagram", "tiktok", "youtube", "youtube_shorts", "generic"]
AspectRatio = Literal["9:16", "16:9", "1:1", "4:5"]
Tone = Literal["luxury", "friendly", "professional", "energetic", "minimal", "cinematic"]


class ProjectSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform = "generic"
    duration_s: Literal[15, 30, 60] = 30
    aspect_ratio: AspectRatio = "9:16"
    tone: Tone = "professional"
    preset: str | None = Field(default=None, max_length=60)
    language: str = Field(default="tr", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")


class ProjectCreate(BaseModel):
    type: ProjectType
    name: Name
    description: LongText = ""
    character_id: str | None = None
    product_id: str | None = None
    property_id: str | None = None
    settings: ProjectSettings = ProjectSettings()


class ProjectUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"name", "description", "settings"})

    name: Name | None = None
    description: LongText | None = None
    character_id: str | None = None
    product_id: str | None = None
    property_id: str | None = None
    settings: ProjectSettings | None = None


class ProjectRead(TimestampedRead):
    type: ProjectType
    name: str
    description: str
    character_id: str | None
    product_id: str | None
    property_id: str | None
    settings: ProjectSettings
