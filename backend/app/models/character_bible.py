from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CharacterBible(TimestampMixin, Base):
    """Consistency sheet for one character.

    Consistency comes from reference images (canonical + views, passed to FLUX.2 as multi-reference
    input) and a stable identity description. Seeds are recorded for reproducibility only.
    """

    __tablename__ = "character_bibles"

    character_id: Mapped[str] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True
    )
    visual_descriptors: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    immutable_traits: Mapped[list[str]] = mapped_column(JSON, default=list)
    mutable_traits: Mapped[list[str]] = mapped_column(JSON, default=list)
    prompt_template: Mapped[str] = mapped_column(Text, default="")
    negative_prompts: Mapped[list[str]] = mapped_column(JSON, default=list)
    generation_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    seed_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    lora: Mapped[dict[str, Any] | None] = mapped_column(JSON)
