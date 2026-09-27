from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import IdPrefix, new_id
from app.models.character import Character
from app.models.enums import ConsentSubject
from app.schemas.character import CharacterCreate, CharacterUpdate
from app.services.consents import require_active_consent
from app.services.crud import apply_updates, get_or_404, paginate


def _enforce_consent(session: Session, character: Character) -> None:
    if character.is_real_person:
        require_active_consent(session, character.consent_id, ConsentSubject.FACE)


def create_character(session: Session, payload: CharacterCreate) -> Character:
    character = Character(id=new_id(IdPrefix.CHARACTER), **payload.model_dump())
    _enforce_consent(session, character)
    session.add(character)
    session.commit()
    return character


def list_characters(session: Session, q: str | None, limit: int, offset: int) -> tuple[list[Character], int]:
    stmt = select(Character).order_by(Character.created_at.desc())
    if q:
        stmt = stmt.where(Character.name.icontains(q, autoescape=True))
    return paginate(session, stmt, limit, offset)


def get_character(session: Session, character_id: str) -> Character:
    return get_or_404(session, Character, character_id, "Character")


def update_character(session: Session, character_id: str, payload: CharacterUpdate) -> Character:
    character = get_character(session, character_id)
    apply_updates(character, payload.model_dump(exclude_unset=True))
    _enforce_consent(session, character)
    session.commit()
    return character


def delete_character(session: Session, character_id: str) -> None:
    session.delete(get_character(session, character_id))
    session.commit()
