from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.enums import ListingType, PropertyCategory
from app.schemas.asset import AssetLinkRead
from app.schemas.common import (
    Currency,
    LongText,
    Name,
    PatchModel,
    ShortText,
    TextList,
    TimestampedRead,
    WebUrl,
)

Price = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]
Area = Annotated[float, Field(gt=0, le=1e9)]
SmallCount = Annotated[int, Field(ge=0, le=1_000)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
# Turkish listings use "3+1" style room counts; keep as verified free text.
Rooms = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


class _PropertyFacts(BaseModel):
    """Verified listing facts. Unknown values must stay null — the app never infers them."""

    listing_type: ListingType | None = None
    property_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    price: Price | None = None
    currency: Currency | None = None
    location: ShortText | None = None
    square_meters: Area | None = None
    land_square_meters: Area | None = None
    rooms: Rooms | None = None
    bathrooms: SmallCount | None = None
    floors: SmallCount | None = None
    building_age: SmallCount | None = None
    features: TextList | None = None
    description: LongText | None = None
    contact: ShortText | None = None
    website: WebUrl | None = None
    zoning: ShortText | None = None
    parcel_info: ShortText | None = None
    road_access: bool | None = None
    electricity: bool | None = None
    water: bool | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    facts_source: ShortText | None = None


def _check_pairs(model: BaseModel) -> None:
    fields = model.model_fields_set
    values = model.__dict__
    if "price" in fields and values.get("price") is not None and values.get("currency") is None:
        raise ValueError("currency is required when price is set")
    if ("latitude" in fields) != ("longitude" in fields) or (
        (values.get("latitude") is None) != (values.get("longitude") is None)
    ):
        raise ValueError("latitude and longitude must be provided together")


class PropertyCreate(_PropertyFacts):
    category: PropertyCategory
    title: Name
    mark_facts_verified: bool = Field(
        default=False, description="Set when the user confirms all entered facts are accurate."
    )

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _check_pairs(self)
        return self


class PropertyUpdate(_PropertyFacts, PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset(
        {"title", "description", "features", "mark_facts_verified"}
    )

    title: Name | None = None
    mark_facts_verified: bool | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _check_pairs(self)
        return self


class PropertyRead(TimestampedRead):
    category: PropertyCategory
    title: str
    listing_type: ListingType | None
    property_type: str | None
    price: Decimal | None
    currency: str | None
    location: str | None
    square_meters: float | None
    land_square_meters: float | None
    rooms: str | None
    bathrooms: int | None
    floors: int | None
    building_age: int | None
    features: list[str]
    description: str
    contact: str | None
    website: str | None
    zoning: str | None
    parcel_info: str | None
    road_access: bool | None
    electricity: bool | None
    water: bool | None
    latitude: float | None
    longitude: float | None
    facts_verified_at: datetime | None
    facts_source: str | None
    assets: list[AssetLinkRead]


class PropertySummary(TimestampedRead):
    category: PropertyCategory
    title: str
    location: str | None
    price: Decimal | None
    currency: str | None
    facts_verified_at: datetime | None
