from __future__ import annotations

from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.safety import find_minor_reference
from app.schemas.asset import AssetRead
from app.schemas.common import TimestampedRead
from app.services.prompts.character import CharacterPurpose

MAX_SEED = 2**32 - 1

Prompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ImageGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: Prompt
    width: int = Field(default=1024, ge=64, le=4096)
    height: int = Field(default=1024, ge=64, le=4096)
    steps: int | None = Field(default=None, ge=1, le=150)
    guidance_scale: float | None = Field(default=None, ge=0, le=30)
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED - 16)
    num_images: int = Field(default=1, ge=1, le=4)
    model_key: str | None = Field(default=None, max_length=80)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=10)
    project_id: str | None = None
    character_id: str | None = None
    watermark: bool | None = Field(default=None, description="Defaults to the 'AI watermark' setting.")
    purpose: CharacterPurpose | None = Field(default=None, description="Set by Character Studio workflows.")

    @model_validator(mode="after")
    def _adult_only(self) -> Self:
        if hit := find_minor_reference(self.prompt):
            raise ValueError(f"prompt: only adult subjects are supported; remove '{hit}'")
        return self


class GenerationRead(TimestampedRead):
    kind: str
    job_id: str | None
    project_id: str | None
    character_id: str | None
    provider: str
    model_key: str
    model_source: str | None
    params: dict[str, Any]
    seeds: list[int]
    input_asset_ids: list[str]
    output_asset_ids: list[str]
    duration_ms: int
    assets: list[AssetRead] = Field(default_factory=list)
