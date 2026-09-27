from __future__ import annotations

from typing import Any

from pydantic import Field

from app.models.enums import AssetKind, AssetRole, AssetSource
from app.schemas.common import ORMModel, TimestampedRead


class AssetRead(TimestampedRead):
    kind: AssetKind
    source: AssetSource
    mime: str
    size_bytes: int
    checksum_sha256: str
    width: int | None
    height: int | None
    duration_s: float | None
    original_filename: str | None
    ai_generated: bool
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")


class AssetLinkCreate(ORMModel):
    asset_id: str
    role: AssetRole
    position: int = Field(default=0, ge=0, le=10_000)


class AssetLinkRead(ORMModel):
    role: AssetRole
    position: int
    asset: AssetRead
