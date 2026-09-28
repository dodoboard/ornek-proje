from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ConsentRequiredError
from app.core.ids import IdPrefix, new_id
from app.db.base import utcnow
from app.models.consent import Consent
from app.models.enums import ConsentSubject
from app.schemas.consent import CONSENT_STATEMENTS, ConsentCreate
from app.services.assets import get_asset
from app.services.crud import get_or_404, paginate


def create_consent(session: Session, payload: ConsentCreate) -> Consent:
    if payload.evidence_asset_id is not None:
        get_asset(session, payload.evidence_asset_id)
    consent = Consent(
        id=new_id(IdPrefix.CONSENT),
        subject_type=payload.subject_type,
        subject_name=payload.subject_name,
        statement=CONSENT_STATEMENTS[payload.subject_type],
        granted_by=payload.granted_by,
        granted_at=utcnow(),
        evidence_asset_id=payload.evidence_asset_id,
    )
    session.add(consent)
    session.commit()
    return consent


def list_consents(session: Session, limit: int, offset: int) -> tuple[list[Consent], int]:
    return paginate(session, select(Consent).order_by(Consent.created_at.desc()), limit, offset)


def get_consent(session: Session, consent_id: str) -> Consent:
    return get_or_404(session, Consent, consent_id, "Consent")


def revoke_consent(session: Session, consent_id: str) -> Consent:
    consent = get_consent(session, consent_id)
    if consent.revoked_at is not None:
        raise ConflictError("Consent is already revoked.")
    consent.revoked_at = utcnow()
    session.commit()
    return consent


def require_active_consent(session: Session, consent_id: str | None, subject: ConsentSubject) -> Consent:
    if consent_id is None:
        raise ConsentRequiredError()
    consent = session.get(Consent, consent_id)
    if consent is None or not consent.is_active or consent.subject_type is not subject:
        raise ConsentRequiredError(
            f"An active '{subject.value}' consent record is required for a real person."
        )
    return consent
