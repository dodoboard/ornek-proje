from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UTCDateTime, id_column
from app.models.enums import ConsentSubject, enum_column


class Consent(TimestampMixin, Base):
    """Record that the user has permission to use a real person's likeness or voice."""

    __tablename__ = "consents"

    id: Mapped[str] = id_column()
    subject_type: Mapped[ConsentSubject] = mapped_column(enum_column(ConsentSubject, "consent_subject"))
    subject_name: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    granted_by: Mapped[str] = mapped_column(String(200))
    granted_at: Mapped[datetime] = mapped_column(UTCDateTime())
    evidence_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"))
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
