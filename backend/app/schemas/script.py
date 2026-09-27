"""Script + storyboard schemas. `ScriptDraft` is also the JSON schema the local LLM must follow."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.safety import find_minor_reference
from app.schemas.common import TimestampedRead

ShotType = Literal[
    "hook",
    "talking_head",
    "product_closeup",
    "product_in_use",
    "broll",
    "property_exterior",
    "property_interior",
    "land_overview",
    "text_card",
    "cta",
]
CameraShot = Literal["wide", "medium", "close_up", "extreme_close_up", "over_the_shoulder", "top_down"]
CameraMotion = Literal[
    "static", "slow_push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down", "orbit", "handheld"
]
GenerationMethod = Literal[
    "ai_image", "ai_video", "ffmpeg_motion", "real_footage", "lipsync", "product_composite"
]
DisclosureLabel = Literal[
    "ai_generated", "ai_enhanced", "representative_visualization", "real_footage", "no_ai"
]

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Medium = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]

#: Sensible defaults per shot type; users can change them per shot.
DEFAULT_METHOD: dict[str, GenerationMethod] = {
    "hook": "ai_video",
    "talking_head": "lipsync",
    "product_closeup": "product_composite",
    "product_in_use": "ai_video",
    "broll": "ai_video",
    "property_exterior": "real_footage",
    "property_interior": "real_footage",
    "land_overview": "real_footage",
    "text_card": "ffmpeg_motion",
    "cta": "ffmpeg_motion",
}
DEFAULT_DISCLOSURE: dict[GenerationMethod, DisclosureLabel] = {
    "ai_image": "ai_generated",
    "ai_video": "ai_generated",
    "lipsync": "ai_generated",
    "product_composite": "ai_enhanced",
    "ffmpeg_motion": "no_ai",
    "real_footage": "real_footage",
}


class ShotDraft(BaseModel):
    """One shot as written by the LLM (facts only as {{placeholders}})."""

    model_config = ConfigDict(extra="forbid")

    type: ShotType
    duration_s: float = Field(ge=1, le=15)
    description: Medium = ""
    dialogue: Medium = ""
    on_screen_text: Short = ""
    visual_prompt: Medium = ""
    camera: CameraShot = "medium"
    camera_motion: CameraMotion = "static"


class ScriptDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Short
    hook: Short
    shots: list[ShotDraft] = Field(min_length=2, max_length=12)
    cta: Short = ""


def llm_schema() -> dict[str, Any]:
    return ScriptDraft.model_json_schema()


# --------------------------------------------------------------------------- API


class ScriptGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = Field(
        default="", description="Your notes for the script (treated as verified input)."
    )
    llm_model_key: str | None = Field(default=None, max_length=80)
    template_only: bool = Field(default=False, description="Skip the LLM and use the deterministic template.")

    @model_validator(mode="after")
    def _adult_only(self) -> Self:
        if hit := find_minor_reference(self.brief):
            raise ValueError(f"brief: only adult subjects are supported; remove '{hit}'")
        return self


class ShotRead(TimestampedRead):
    storyboard_id: str
    position: int
    type: str
    duration_s: float
    description: str
    dialogue: str
    on_screen_text: str
    visual_prompt: str
    camera: str
    camera_motion: str
    generation_method: str
    disclosure_label: str
    edited: bool
    status: str
    keyframe_asset_id: str | None
    clip_asset_id: str | None


class StoryboardRead(TimestampedRead):
    project_id: str
    script_id: str | None
    version: int
    aspect_ratio: str
    shots: list[ShotRead]
    total_duration_s: float


class ScriptRead(TimestampedRead):
    project_id: str
    source: str
    llm_model: str | None
    language: str
    title: str
    hook: str
    cta: str
    brief: str
    attempts: list[dict[str, Any]]
    fact_report: dict[str, Any]


class ShotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ShotType | None = None
    duration_s: float | None = Field(default=None, ge=0.5, le=60)
    description: Medium | None = None
    dialogue: Medium | None = None
    on_screen_text: Short | None = None
    visual_prompt: Medium | None = None
    camera: CameraShot | None = None
    camera_motion: CameraMotion | None = None
    generation_method: GenerationMethod | None = None
    disclosure_label: DisclosureLabel | None = None

    @model_validator(mode="after")
    def _adult_only(self) -> Self:
        for text in (self.description, self.dialogue, self.on_screen_text, self.visual_prompt):
            if text and (hit := find_minor_reference(text)):
                raise ValueError(f"only adult subjects are supported; remove '{hit}'")
        return self


class ShotCreate(ShotUpdate):
    type: ShotType = "broll"
    duration_s: float | None = Field(default=3, ge=0.5, le=60)
    position: int | None = Field(default=None, ge=0, description="Insert position (default: end).")


class ShotOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_ids: list[str] = Field(min_length=1, max_length=100)
