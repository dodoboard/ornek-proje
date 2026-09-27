from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import PaginationDep, SearchQuery, SessionDep
from app.models.links import ProductAsset
from app.schemas.asset import AssetLinkCreate
from app.schemas.common import Page
from app.schemas.product import ProductCreate, ProductRead, ProductSummary, ProductUpdate
from app.services import asset_links
from app.services import products as service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=Page[ProductSummary])
def list_products(session: SessionDep, page: PaginationDep, q: SearchQuery = None) -> Page[ProductSummary]:
    items, total = service.list_products(session, q, page.limit, page.offset)
    return Page(items=[ProductSummary.model_validate(i) for i in items], total=total, **page.__dict__)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, session: SessionDep) -> ProductRead:
    return ProductRead.model_validate(service.create_product(session, payload))


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, session: SessionDep) -> ProductRead:
    return ProductRead.model_validate(service.get_product(session, product_id))


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: str, payload: ProductUpdate, session: SessionDep) -> ProductRead:
    return ProductRead.model_validate(service.update_product(session, product_id, payload))


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: str, session: SessionDep) -> None:
    service.delete_product(session, product_id)


@router.post("/{product_id}/assets", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def attach_asset(product_id: str, payload: AssetLinkCreate, session: SessionDep) -> ProductRead:
    product = service.get_product(session, product_id)
    return ProductRead.model_validate(asset_links.attach_to_product(session, product, payload))


@router.delete("/{product_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_asset(product_id: str, asset_id: str, session: SessionDep) -> None:
    service.get_product(session, product_id)
    asset_links.detach(session, ProductAsset, "product_id", product_id, asset_id)
