"""Scripts (LLM or template output), versioned storyboards and their editable shots."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, id_column


class Script(TimestampMixin, Base):
    __tablename__ = "scripts"

    id: Mapped[str] = id_column()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # llm | template
    llm_model: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200), default="")
    hook: Mapped[str] = mapped_column(String(200), default="")
    cta: Mapped[str] = mapped_column(String(200), default="")
    brief: Mapped[str] = mapped_column(Text, default="")
    #: The draft exactly as validated, with {{placeholders}} (facts are rendered only on the storyboard).
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    fact_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Shot(TimestampMixin, Base):
    __tablename__ = "shots"

    id: Mapped[str] = id_column()
    storyboard_id: Mapped[str] = mapped_column(ForeignKey("storyboards.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(40))
    duration_s: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, default="")
    dialogue: Mapped[str] = mapped_column(Text, default="")
    on_screen_text: Mapped[str] = mapped_column(String(200), default="")
    visual_prompt: Mapped[str] = mapped_column(Text, default="")
    camera: Mapped[str] = mapped_column(String(40), default="medium")
    camera_motion: Mapped[str] = mapped_column(String(40), default="static")
    generation_method: Mapped[str] = mapped_column(String(40))
    disclosure_label: Mapped[str] = mapped_column(String(40))
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    keyframe_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    clip_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))


class Storyboard(TimestampMixin, Base):
    __tablename__ = "storyboards"

    id: Mapped[str] = id_column()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    script_id: Mapped[str | None] = mapped_column(ForeignKey("scripts.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer)
    aspect_ratio: Mapped[str] = mapped_column(String(8))

    shots: Mapped[list[Shot]] = relationship(
        cascade="all, delete-orphan", order_by=Shot.position, lazy="selectin"
    )

    @property
    def total_duration_s(self) -> float:
        return round(sum(s.duration_s for s in self.shots), 2)
