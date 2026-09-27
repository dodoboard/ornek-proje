"""Owner ↔ asset association tables (character/product/property)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.asset import Asset
from app.models.enums import AssetRole, enum_column


class _AssetLinkMixin(TimestampMixin):
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), primary_key=True)
    role: Mapped[AssetRole] = mapped_column(enum_column(AssetRole, "asset_role"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class CharacterAsset(_AssetLinkMixin, Base):
    __tablename__ = "character_assets"

    character_id: Mapped[str] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True
    )
    asset: Mapped[Asset] = relationship(lazy="joined")


class ProductAsset(_AssetLinkMixin, Base):
    __tablename__ = "product_assets"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    asset: Mapped[Asset] = relationship(lazy="joined")


class PropertyAsset(_AssetLinkMixin, Base):
    __tablename__ = "property_assets"

    property_id: Mapped[str] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True
    )
    asset: Mapped[Asset] = relationship(lazy="joined")
