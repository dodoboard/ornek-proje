from __future__ import annotations

from typing import Annotated, Any, Literal, Self

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


EditMode = Literal["edit", "inpaint", "outpaint"]
DEFAULT_STRENGTH: dict[str, float] = {"inpaint": 0.9, "outpaint": 1.0}


class Padding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: int = Field(default=0, ge=0, le=1024)
    top: int = Field(default=0, ge=0, le=1024)
    right: int = Field(default=0, ge=0, le=1024)
    bottom: int = Field(default=0, ge=0, le=1024)

    @model_validator(mode="after")
    def _multiples_of_16(self) -> Self:
        values = (self.left, self.top, self.right, self.bottom)
        if any(v % 16 for v in values):
            raise ValueError("padding values must be multiples of 16")
        if not any(values):
            raise ValueError("padding must extend at least one side")
        return self


class ImageEditRequest(BaseModel):
    """Edit an existing image: instruction edit, masked inpaint or outpaint."""

    model_config = ConfigDict(extra="forbid")

    mode: EditMode
    source_asset_id: str
    prompt: Prompt
    mask_asset_id: str | None = None
    padding: Padding | None = None
    strength: float | None = Field(default=None, ge=0.05, le=1.0)
    feather: int = Field(default=8, ge=0, le=64, description="Soft edge (px) when blending into the original")
    steps: int | None = Field(default=None, ge=1, le=150)
    guidance_scale: float | None = Field(default=None, ge=0, le=30)
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED - 16)
    num_images: int = Field(default=1, ge=1, le=4)
    model_key: str | None = Field(default=None, max_length=80)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=10)
    project_id: str | None = None
    character_id: str | None = None
    watermark: bool | None = None

    @model_validator(mode="after")
    def _mode_inputs(self) -> Self:
        if hit := find_minor_reference(self.prompt):
            raise ValueError(f"prompt: only adult subjects are supported; remove '{hit}'")
        if self.mode == "inpaint" and not self.mask_asset_id:
            raise ValueError("inpaint needs mask_asset_id (white = area to change)")
        if self.mode == "outpaint" and self.padding is None:
            raise ValueError("outpaint needs padding")
        if self.mode != "inpaint" and self.mask_asset_id:
            raise ValueError("mask_asset_id is only used for inpaint")
        if self.mode != "outpaint" and self.padding is not None:
            raise ValueError("padding is only used for outpaint")
        if self.mode == "edit" and self.strength is not None:
            raise ValueError("strength is not used for instruction edits")
        return self

    @property
    def effective_strength(self) -> float:
        return self.strength if self.strength is not None else DEFAULT_STRENGTH.get(self.mode, 1.0)


class GenerationRead(TimestampedRead):
    kind: str
    job_id: str | None
    project_id: str | None
    character_id: str | None
    product_id: str | None = None
    provider: str
    model_key: str
    model_source: str | None
    params: dict[str, Any]
    seeds: list[int]
    input_asset_ids: list[str]
    output_asset_ids: list[str]
    duration_ms: int
    assets: list[AssetRead] = Field(default_factory=list)
