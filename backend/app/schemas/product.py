from __future__ import annotations

from decimal import Decimal
from typing import Annotated, ClassVar, Self

from pydantic import BaseModel, Field, model_validator

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

Price = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class _PriceCurrency(BaseModel):
    @model_validator(mode="after")
    def _currency_with_price(self) -> Self:
        price = getattr(self, "price", None)
        currency = getattr(self, "currency", None)
        if price is not None and currency is None:
            raise ValueError("currency is required when price is set")
        return self


class ProductCreate(_PriceCurrency):
    name: Name
    brand: ShortText = ""
    description: LongText = ""
    features: TextList = []
    price: Price | None = None
    currency: Currency | None = None
    cta: ShortText = ""
    website: WebUrl | None = None


class ProductUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"name", "brand", "description", "features", "cta"})

    name: Name | None = None
    brand: ShortText | None = None
    description: LongText | None = None
    features: TextList | None = None
    price: Price | None = None
    currency: Currency | None = None
    cta: ShortText | None = None
    website: WebUrl | None = None


class ProductRead(TimestampedRead):
    name: str
    brand: str
    description: str
    features: list[str]
    price: Decimal | None
    currency: str | None
    cta: str
    website: str | None
    assets: list[AssetLinkRead]


class ProductSummary(TimestampedRead):
    name: str
    brand: str
    price: Decimal | None
    currency: str | None
