"""Video generation requests (image-to-video, text-to-video, camera motion)."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.safety import find_minor_reference
from app.schemas.generation import MAX_SEED
from app.schemas.script import CameraMotion

OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class VideoGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: OptionalText = Field(
        default="", description="Required for AI models; optional for camera motion."
    )
    image_asset_id: str | None = Field(default=None, description="First frame (image-to-video).")
    last_image_asset_id: str | None = Field(default=None, description="Last frame, if the model supports it.")
    width: int = Field(default=704, ge=128, le=3840)
    height: int = Field(default=1280, ge=128, le=3840)
    duration_s: float = Field(default=5.0, ge=0.5, le=20)
    fps: int | None = Field(default=None, ge=8, le=60)
    steps: int | None = Field(default=None, ge=1, le=150)
    guidance_scale: float | None = Field(default=None, ge=0, le=30)
    negative_prompt: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED - 16)
    motion: CameraMotion = "static"
    motion_strength: float = Field(default=1.0, ge=0, le=2)
    model_key: str | None = Field(default=None, max_length=80)
    project_id: str | None = None
    character_id: str | None = None
    shot_id: str | None = Field(default=None, description="Storyboard shot that receives this clip.")

    @model_validator(mode="after")
    def _check(self) -> Self:
        for text in (self.prompt, self.negative_prompt or ""):
            if hit := find_minor_reference(text):
                raise ValueError(f"prompt: only adult subjects are supported; remove '{hit}'")
        if self.last_image_asset_id and not self.image_asset_id:
            raise ValueError("last_image_asset_id needs image_asset_id (first frame)")
        return self

    @property
    def reference_asset_ids(self) -> list[str]:
        """Consent/asset checks treat the conditioning images like references."""
        return [a for a in (self.image_asset_id, self.last_image_asset_id) if a]
