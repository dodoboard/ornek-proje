from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, id_column
from app.models.enums import ProjectType, enum_column


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = id_column()
    type: Mapped[ProjectType] = mapped_column(enum_column(ProjectType, "project_type"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    character_id: Mapped[str | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    property_id: Mapped[str | None] = mapped_column(ForeignKey("properties.id", ondelete="SET NULL"))
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
