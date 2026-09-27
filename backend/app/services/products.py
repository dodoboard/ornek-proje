from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import IdPrefix, new_id
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.crud import apply_updates, get_or_404, paginate


class PriceCurrencyError(AppError):
    status_code = 422
    default_message = "Currency is required when a price is set."


def create_product(session: Session, payload: ProductCreate) -> Product:
    product = Product(id=new_id(IdPrefix.PRODUCT), **payload.model_dump())
    session.add(product)
    session.commit()
    return product


def list_products(session: Session, q: str | None, limit: int, offset: int) -> tuple[list[Product], int]:
    stmt = select(Product).order_by(Product.created_at.desc())
    if q:
        stmt = stmt.where(
            or_(Product.name.icontains(q, autoescape=True), Product.brand.icontains(q, autoescape=True))
        )
    return paginate(session, stmt, limit, offset)


def get_product(session: Session, product_id: str) -> Product:
    return get_or_404(session, Product, product_id, "Product")


def update_product(session: Session, product_id: str, payload: ProductUpdate) -> Product:
    product = get_product(session, product_id)
    apply_updates(product, payload.model_dump(exclude_unset=True))
    if product.price is not None and product.currency is None:
        raise PriceCurrencyError()
    session.commit()
    return product


def delete_product(session: Session, product_id: str) -> None:
    session.delete(get_product(session, product_id))
    session.commit()
