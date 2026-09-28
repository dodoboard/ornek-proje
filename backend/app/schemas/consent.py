from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.enums import ConsentSubject
from app.schemas.common import Name, ORMModel, TimestampedRead

CONSENT_STATEMENTS: dict[ConsentSubject, str] = {
    ConsentSubject.FACE: "I have permission to use this person's likeness.",
    ConsentSubject.VOICE: "I have permission to use this person's voice.",
}


class ConsentCreate(ORMModel):
    subject_type: ConsentSubject
    subject_name: Name
    granted_by: Name
    # Explicit opt-in; the stored statement text is fixed server-side.
    confirm: Literal[True] = Field(description="Must be true: confirms the consent statement.")
    evidence_asset_id: str | None = None


class ConsentRead(TimestampedRead):
    subject_type: ConsentSubject
    subject_name: str
    statement: str
    granted_by: str
    granted_at: datetime
    evidence_asset_id: str | None
    revoked_at: datetime | None
    is_active: bool
