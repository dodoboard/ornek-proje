from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import AssetRole
from app.schemas.common import LongText, ORMModel, PatchModel, TextList
from app.services.image_sizes import AspectRatio
from app.services.prompts.character import CharacterPurpose

ViewRole = Literal["canonical", "front", "three_quarter", "full_body"]
VIEW_ROLES: tuple[AssetRole, ...] = (
    AssetRole.CANONICAL,
    AssetRole.FRONT,
    AssetRole.THREE_QUARTER,
    AssetRole.FULL_BODY,
)


class SeedRecord(BaseModel):
    seed: int
    purpose: str
    generation_id: str
    asset_id: str
    model: str
    created_at: datetime


class CharacterBibleRead(ORMModel):
    character_id: str
    visual_descriptors: dict[str, Any]
    immutable_traits: list[str]
    mutable_traits: list[str]
    prompt_template: str
    negative_prompts: list[str]
    generation_settings: dict[str, Any]
    seed_history: list[SeedRecord]
    lora: dict[str, Any] | None
    views: dict[str, str | None] = Field(
        description="role → asset id (canonical, front, three_quarter, full_body)"
    )
    reference_asset_ids: list[str] = Field(description="Uploaded reference photos")
    identity: str = Field(description="Identity description used in every prompt")


class CharacterBibleUpdate(PatchModel):
    model_config = ConfigDict(extra="forbid")
    non_nullable: ClassVar[frozenset[str]] = frozenset(
        {"visual_descriptors", "immutable_traits", "mutable_traits", "prompt_template", "negative_prompts",
         "generation_settings"}
    )  # fmt: skip

    visual_descriptors: dict[str, str] | None = None
    immutable_traits: TextList | None = None
    mutable_traits: TextList | None = None
    prompt_template: LongText | None = Field(default=None, description="House style appended to every prompt")
    negative_prompts: TextList | None = Field(
        default=None, description="Stored for models that support it; FLUX.2 ignores negative prompts."
    )
    generation_settings: dict[str, Any] | None = None
    lora: dict[str, Any] | None = None


class CharacterGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: CharacterPurpose
    scene: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    num_images: int = Field(default=2, ge=1, le=4)
    aspect_ratio: AspectRatio | None = None
    steps: int | None = Field(default=None, ge=1, le=150)
    seed: int | None = Field(default=None, ge=0)
    model_key: str | None = Field(default=None, max_length=80)
    project_id: str | None = None

    @model_validator(mode="after")
    def _scene_needs_text(self) -> Self:
        if self.purpose == "scene" and not self.scene:
            raise ValueError("scene: describe the scene for a scene generation")
        return self


class PromptPreview(BaseModel):
    purpose: CharacterPurpose
    prompt: str
    reference_asset_ids: list[str]
    width: int
    height: int


class SetViewRequest(BaseModel):
    asset_id: str
