from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import PaginationDep, SearchQuery, SessionDep
from app.models.enums import PropertyCategory
from app.models.links import PropertyAsset
from app.schemas.asset import AssetLinkCreate
from app.schemas.common import Page
from app.schemas.property import PropertyCreate, PropertyRead, PropertySummary, PropertyUpdate
from app.services import asset_links
from app.services import properties as service

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=Page[PropertySummary])
def list_properties(
    session: SessionDep,
    page: PaginationDep,
    category: PropertyCategory | None = None,
    q: SearchQuery = None,
) -> Page[PropertySummary]:
    items, total = service.list_properties(session, category, q, page.limit, page.offset)
    return Page(items=[PropertySummary.model_validate(i) for i in items], total=total, **page.__dict__)


@router.post("", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
def create_property(payload: PropertyCreate, session: SessionDep) -> PropertyRead:
    return PropertyRead.model_validate(service.create_property(session, payload))


@router.get("/{property_id}", response_model=PropertyRead)
def get_property(property_id: str, session: SessionDep) -> PropertyRead:
    return PropertyRead.model_validate(service.get_property(session, property_id))


@router.patch("/{property_id}", response_model=PropertyRead)
def update_property(property_id: str, payload: PropertyUpdate, session: SessionDep) -> PropertyRead:
    return PropertyRead.model_validate(service.update_property(session, property_id, payload))


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(property_id: str, session: SessionDep) -> None:
    service.delete_property(session, property_id)


@router.post("/{property_id}/assets", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
def attach_asset(property_id: str, payload: AssetLinkCreate, session: SessionDep) -> PropertyRead:
    prop = service.get_property(session, property_id)
    return PropertyRead.model_validate(asset_links.attach_to_property(session, prop, payload))


@router.delete("/{property_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_asset(property_id: str, asset_id: str, session: SessionDep) -> None:
    service.get_property(session, property_id)
    asset_links.detach(session, PropertyAsset, "property_id", property_id, asset_id)
