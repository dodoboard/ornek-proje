from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, id_column
from app.models.links import CharacterAsset

MIN_ADULT_AGE = 18
MAX_AGE = 120


class Character(TimestampMixin, Base):
    __tablename__ = "characters"
    __table_args__ = (
        CheckConstraint(f"adult_age >= {MIN_ADULT_AGE} AND adult_age <= {MAX_AGE}", name="adult_age_range"),
        CheckConstraint("is_real_person = 0 OR consent_id IS NOT NULL", name="real_person_requires_consent"),
    )

    id: Mapped[str] = id_column()
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    adult_age: Mapped[int] = mapped_column(Integer)
    presentation: Mapped[str] = mapped_column(String(60), default="")
    face_description: Mapped[str] = mapped_column(Text, default="")
    hair: Mapped[str] = mapped_column(String(200), default="")
    eye_color: Mapped[str] = mapped_column(String(60), default="")
    skin_appearance: Mapped[str] = mapped_column(String(200), default="")
    body_description: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(200), default="")
    clothing_preferences: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    speaking_style: Mapped[str] = mapped_column(Text, default="")
    brand_tone: Mapped[str] = mapped_column(String(200), default="")
    default_language: Mapped[str] = mapped_column(String(16), default="tr")
    default_prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    preferred_camera_angles: Mapped[list[str]] = mapped_column(JSON, default=list)
    color_palette: Mapped[list[str]] = mapped_column(JSON, default=list)
    voice_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_real_person: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_id: Mapped[str | None] = mapped_column(ForeignKey("consents.id", ondelete="RESTRICT"))

    assets: Mapped[list[CharacterAsset]] = relationship(
        cascade="all, delete-orphan", order_by=CharacterAsset.position, lazy="selectin"
    )
