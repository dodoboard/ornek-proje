from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.ids import IdPrefix, new_id
from app.db.base import utcnow
from app.models.enums import PropertyCategory
from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyUpdate
from app.services.crud import apply_updates, get_or_404, paginate
from app.services.products import PriceCurrencyError

# Editing any of these invalidates a previous "facts verified" confirmation.
FACT_FIELDS = frozenset(
    {
        "listing_type", "property_type", "price", "currency", "location", "square_meters",
        "land_square_meters", "rooms", "bathrooms", "floors", "building_age", "features",
        "zoning", "parcel_info", "road_access", "electricity", "water", "latitude", "longitude",
    }
)  # fmt: skip


def create_property(session: Session, payload: PropertyCreate) -> Property:
    data = payload.model_dump(exclude={"mark_facts_verified"}, exclude_none=True)
    prop = Property(id=new_id(IdPrefix.PROPERTY), **data)
    if payload.mark_facts_verified:
        prop.facts_verified_at = utcnow()
    session.add(prop)
    session.commit()
    return prop


def list_properties(
    session: Session, category: PropertyCategory | None, q: str | None, limit: int, offset: int
) -> tuple[list[Property], int]:
    stmt = select(Property).order_by(Property.created_at.desc())
    if category is not None:
        stmt = stmt.where(Property.category == category)
    if q:
        stmt = stmt.where(
            or_(Property.title.icontains(q, autoescape=True), Property.location.icontains(q, autoescape=True))
        )
    return paginate(session, stmt, limit, offset)


def get_property(session: Session, property_id: str) -> Property:
    return get_or_404(session, Property, property_id, "Property")


def update_property(session: Session, property_id: str, payload: PropertyUpdate) -> Property:
    prop = get_property(session, property_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"mark_facts_verified"})

    facts_changed = any(getattr(prop, key) != value for key, value in changes.items() if key in FACT_FIELDS)
    apply_updates(prop, changes)
    if prop.price is not None and prop.currency is None:
        raise PriceCurrencyError()

    if payload.mark_facts_verified:
        prop.facts_verified_at = utcnow()
    elif facts_changed or payload.mark_facts_verified is False:
        prop.facts_verified_at = None
    session.commit()
    return prop


def delete_property(session: Session, property_id: str) -> None:
    session.delete(get_property(session, property_id))
    session.commit()
