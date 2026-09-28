from __future__ import annotations

from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, id_column
from app.models.links import ProductAsset


class Product(TimestampMixin, Base):
    """All fields are user-provided verified facts; generated copy lives elsewhere."""

    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price IS NULL OR price >= 0", name="price_non_negative"),)

    id: Mapped[str] = id_column()
    name: Mapped[str] = mapped_column(String(200), index=True)
    brand: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    cta: Mapped[str] = mapped_column(String(200), default="")
    website: Mapped[str | None] = mapped_column(String(500))

    assets: Mapped[list[ProductAsset]] = relationship(
        cascade="all, delete-orphan", order_by=ProductAsset.position, lazy="selectin"
    )
