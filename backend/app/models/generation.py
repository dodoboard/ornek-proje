from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, id_column


class Generation(TimestampMixin, Base):
    """Provenance of one generation run: model, parameters, seeds and produced assets."""

    __tablename__ = "generations"

    id: Mapped[str] = id_column()
    kind: Mapped[str] = mapped_column(String(20), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    character_id: Mapped[str | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(60))
    model_key: Mapped[str] = mapped_column(String(80))
    model_source: Mapped[str | None] = mapped_column(String(500))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    seeds: Mapped[list[int]] = mapped_column(JSON, default=list)
    input_asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    device: Mapped[dict[str, Any] | None] = mapped_column(JSON)
