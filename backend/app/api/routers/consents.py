from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import PaginationDep, SessionDep
from app.schemas.common import Page
from app.schemas.consent import ConsentCreate, ConsentRead
from app.services import consents as service

router = APIRouter(prefix="/consents", tags=["consents"])


@router.get("", response_model=Page[ConsentRead])
def list_consents(session: SessionDep, page: PaginationDep) -> Page[ConsentRead]:
    items, total = service.list_consents(session, page.limit, page.offset)
    return Page(items=[ConsentRead.model_validate(i) for i in items], total=total, **page.__dict__)


@router.post("", response_model=ConsentRead, status_code=status.HTTP_201_CREATED)
def create_consent(payload: ConsentCreate, session: SessionDep) -> ConsentRead:
    return ConsentRead.model_validate(service.create_consent(session, payload))


@router.get("/{consent_id}", response_model=ConsentRead)
def get_consent(consent_id: str, session: SessionDep) -> ConsentRead:
    return ConsentRead.model_validate(service.get_consent(session, consent_id))


@router.post("/{consent_id}/revoke", response_model=ConsentRead)
def revoke_consent(consent_id: str, session: SessionDep) -> ConsentRead:
    return ConsentRead.model_validate(service.revoke_consent(session, consent_id))
