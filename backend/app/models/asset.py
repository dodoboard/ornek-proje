from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, id_column
from app.models.enums import AssetKind, AssetSource, enum_column


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[str] = id_column()
    kind: Mapped[AssetKind] = mapped_column(enum_column(AssetKind, "asset_kind"), index=True)
    source: Mapped[AssetSource] = mapped_column(enum_column(AssetSource, "asset_source"))
    # Path relative to DATA_DIR, POSIX separators. Never derived from user input.
    path: Mapped[str] = mapped_column(String(512), unique=True)
    mime: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
