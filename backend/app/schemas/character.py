from __future__ import annotations

from typing import Annotated, Any, ClassVar, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.safety import find_minor_reference
from app.models.character import MAX_AGE, MIN_ADULT_AGE
from app.schemas.asset import AssetLinkRead
from app.schemas.common import (
    HexColor,
    LanguageCode,
    LongText,
    PatchModel,
    ShortText,
    TextList,
    TimestampedRead,
)

AdultAge = Annotated[int, Field(ge=MIN_ADULT_AGE, le=MAX_AGE)]
CharacterName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Palette = Annotated[list[HexColor], Field(max_length=12)]

_SCREENED_FIELDS = (
    "name",
    "description",
    "presentation",
    "face_description",
    "hair",
    "skin_appearance",
    "body_description",
    "style",
    "clothing_preferences",
    "personality",
    "speaking_style",
    "default_prompt",
)


class _MinorScreen(BaseModel):
    @model_validator(mode="after")
    def _reject_minor_references(self) -> Self:
        for field_name in _SCREENED_FIELDS:
            value = getattr(self, field_name, None)
            if isinstance(value, str) and (hit := find_minor_reference(value)):
                raise ValueError(f"{field_name}: characters must be adults; remove '{hit}'")
        return self


class CharacterCreate(_MinorScreen):
    name: CharacterName
    adult_age: AdultAge
    description: LongText = ""
    presentation: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""
    face_description: LongText = ""
    hair: ShortText = ""
    eye_color: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""
    skin_appearance: ShortText = ""
    body_description: LongText = ""
    style: ShortText = ""
    clothing_preferences: LongText = ""
    personality: LongText = ""
    speaking_style: LongText = ""
    brand_tone: ShortText = ""
    default_language: LanguageCode = "tr"
    default_prompt: LongText = ""
    negative_prompt: LongText = ""
    preferred_camera_angles: TextList = []
    color_palette: Palette = []
    voice_profile: dict[str, Any] = {}
    is_real_person: bool = False
    consent_id: str | None = None


class CharacterUpdate(_MinorScreen, PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset(CharacterCreate.model_fields) - {"consent_id"}

    name: CharacterName | None = None
    adult_age: AdultAge | None = None
    description: LongText | None = None
    presentation: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    face_description: LongText | None = None
    hair: ShortText | None = None
    eye_color: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    skin_appearance: ShortText | None = None
    body_description: LongText | None = None
    style: ShortText | None = None
    clothing_preferences: LongText | None = None
    personality: LongText | None = None
    speaking_style: LongText | None = None
    brand_tone: ShortText | None = None
    default_language: LanguageCode | None = None
    default_prompt: LongText | None = None
    negative_prompt: LongText | None = None
    preferred_camera_angles: TextList | None = None
    color_palette: Palette | None = None
    voice_profile: dict[str, Any] | None = None
    is_real_person: bool | None = None
    consent_id: str | None = None


class CharacterRead(TimestampedRead):
    name: str
    adult_age: int
    description: str
    presentation: str
    face_description: str
    hair: str
    eye_color: str
    skin_appearance: str
    body_description: str
    style: str
    clothing_preferences: str
    personality: str
    speaking_style: str
    brand_tone: str
    default_language: str
    default_prompt: str
    negative_prompt: str
    preferred_camera_angles: list[str]
    color_palette: list[str]
    voice_profile: dict[str, Any]
    is_real_person: bool
    consent_id: str | None
    assets: list[AssetLinkRead]


class CharacterSummary(TimestampedRead):
    name: str
    adult_age: int
    style: str
    default_language: str
    is_real_person: bool
