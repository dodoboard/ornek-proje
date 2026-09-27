"""Product Studio requests: cutout (segmentation) and product scenes (composited original pixels)."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.safety import find_minor_reference
from app.schemas.generation import MAX_SEED

SceneText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ProductCutoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_asset_id: str = Field(description="Product photo (attached to the product as product_photo).")
    model_key: str | None = Field(default=None, max_length=80, description="Segmentation model.")
    mask_asset_id: str | None = Field(
        default=None, description="Optional hand-made mask (white = product); skips segmentation."
    )


class PlacementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(default=0.5, ge=0, le=1, description="Horizontal centre of the product (0..1).")
    y: float = Field(default=0.85, ge=0, le=1, description="Bottom edge of the product (0..1).")
    height_ratio: float = Field(default=0.5, ge=0.05, le=1, description="Product height / image height.")
    native_scale: bool = Field(default=False, description="Keep the cutout's pixel size (no resampling).")


class HarmonizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    ring_px: int = Field(default=6, ge=2, le=16, description="Edge band (px) the model may repaint.")
    strength: float = Field(default=0.35, ge=0.1, le=0.8)


class ProductSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutout_asset_id: str
    scene: SceneText
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    placement: PlacementIn = Field(default_factory=PlacementIn)
    shadow: bool = True
    shadow_opacity: float = Field(default=0.45, ge=0, le=0.9)
    harmonize: HarmonizeIn = Field(default_factory=HarmonizeIn)
    background_asset_id: str | None = Field(
        default=None, description="Use this photo as the background instead of generating one."
    )
    steps: int | None = Field(default=None, ge=1, le=150)
    guidance_scale: float | None = Field(default=None, ge=0, le=30)
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED - 16)
    num_images: int = Field(default=1, ge=1, le=4)
    model_key: str | None = Field(default=None, max_length=80, description="Image model (background/edges).")
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=10)
    project_id: str | None = None
    character_id: str | None = Field(
        default=None, description="Influencer shown in the scene (via reference images); consent is checked."
    )
    watermark: bool | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if hit := find_minor_reference(self.scene):
            raise ValueError(f"scene: only adult subjects are supported; remove '{hit}'")
        if self.width % 16 or self.height % 16:
            raise ValueError("width and height must be multiples of 16")
        if self.background_asset_id and not self.harmonize.enabled and self.num_images > 1:
            raise ValueError("with your own background and no edge harmonisation there is only one result")
        return self

    @property
    def uses_model(self) -> bool:
        return self.background_asset_id is None or self.harmonize.enabled
