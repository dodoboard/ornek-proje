from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import PaginationDep, SearchQuery, SessionDep
from app.models.links import CharacterAsset
from app.schemas.asset import AssetLinkCreate
from app.schemas.character import CharacterCreate, CharacterRead, CharacterSummary, CharacterUpdate
from app.schemas.common import Page
from app.services import asset_links
from app.services import characters as service

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=Page[CharacterSummary])
def list_characters(
    session: SessionDep, page: PaginationDep, q: SearchQuery = None
) -> Page[CharacterSummary]:
    items, total = service.list_characters(session, q, page.limit, page.offset)
    return Page(items=[CharacterSummary.model_validate(i) for i in items], total=total, **page.__dict__)


@router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def create_character(payload: CharacterCreate, session: SessionDep) -> CharacterRead:
    return CharacterRead.model_validate(service.create_character(session, payload))


@router.get("/{character_id}", response_model=CharacterRead)
def get_character(character_id: str, session: SessionDep) -> CharacterRead:
    return CharacterRead.model_validate(service.get_character(session, character_id))


@router.patch("/{character_id}", response_model=CharacterRead)
def update_character(character_id: str, payload: CharacterUpdate, session: SessionDep) -> CharacterRead:
    return CharacterRead.model_validate(service.update_character(session, character_id, payload))


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(character_id: str, session: SessionDep) -> None:
    service.delete_character(session, character_id)


@router.post("/{character_id}/assets", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def attach_asset(character_id: str, payload: AssetLinkCreate, session: SessionDep) -> CharacterRead:
    character = service.get_character(session, character_id)
    return CharacterRead.model_validate(asset_links.attach_to_character(session, character, payload))


@router.delete("/{character_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_asset(character_id: str, asset_id: str, session: SessionDep) -> None:
    service.get_character(session, character_id)
    asset_links.detach(session, CharacterAsset, "character_id", character_id, asset_id)
