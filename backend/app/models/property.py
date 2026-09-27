from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, CheckConstraint, Float, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime, id_column
from app.models.enums import ListingType, PropertyCategory, enum_column
from app.models.links import PropertyAsset


class Property(TimestampMixin, Base):
    """Real estate or land listing. Every fact is user-provided; NULL means unknown, never guessed."""

    __tablename__ = "properties"
    __table_args__ = (
        CheckConstraint("price IS NULL OR price >= 0", name="price_non_negative"),
        CheckConstraint("latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="latitude_range"),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="longitude_range"
        ),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinates_pair"),
    )

    id: Mapped[str] = id_column()
    category: Mapped[PropertyCategory] = mapped_column(
        enum_column(PropertyCategory, "property_category"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), index=True)
    listing_type: Mapped[ListingType | None] = mapped_column(enum_column(ListingType, "listing_type"))
    property_type: Mapped[str | None] = mapped_column(String(60))
    price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    location: Mapped[str | None] = mapped_column(String(300))
    square_meters: Mapped[float | None] = mapped_column(Float)
    land_square_meters: Mapped[float | None] = mapped_column(Float)
    rooms: Mapped[str | None] = mapped_column(String(20))
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    floors: Mapped[int | None] = mapped_column(Integer)
    building_age: Mapped[int | None] = mapped_column(Integer)
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    contact: Mapped[str | None] = mapped_column(String(300))
    website: Mapped[str | None] = mapped_column(String(500))

    # Land-specific verified fields
    zoning: Mapped[str | None] = mapped_column(String(300))
    parcel_info: Mapped[str | None] = mapped_column(String(300))
    road_access: Mapped[bool | None] = mapped_column(Boolean)
    electricity: Mapped[bool | None] = mapped_column(Boolean)
    water: Mapped[bool | None] = mapped_column(Boolean)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    facts_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    facts_source: Mapped[str | None] = mapped_column(String(300))

    assets: Mapped[list[PropertyAsset]] = relationship(
        cascade="all, delete-orphan", order_by=PropertyAsset.position, lazy="selectin"
    )
