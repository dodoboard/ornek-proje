from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, ClassVar, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _currency(value: str) -> str:
    upper = value.upper()
    if not _CURRENCY_RE.match(upper):
        raise ValueError("currency must be a 3-letter ISO 4217 code")
    return upper


_HTTP_URL = TypeAdapter(HttpUrl)


def _http_url(value: str) -> str:
    return str(_HTTP_URL.validate_python(value))


def _clean_list(values: list[str]) -> list[str]:
    return [v.strip() for v in values if v.strip()]


def _hex_color(value: str) -> str:
    if not _HEX_COLOR_RE.match(value):
        raise ValueError("color must be #RRGGBB")
    return value.upper()


Currency = Annotated[str, AfterValidator(_currency)]
WebUrl = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500), AfterValidator(_http_url)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)]
LanguageCode = Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")]
HexColor = Annotated[str, AfterValidator(_hex_color)]
TextList = Annotated[
    list[Annotated[str, StringConstraints(max_length=300)]],
    Field(max_length=50),
    AfterValidator(_clean_list),
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampedRead(ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class PatchModel(BaseModel):
    """PATCH body: omitted = unchanged; explicit null only allowed for nullable columns."""

    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_nulls(self) -> Self:
        bad = sorted(f for f in self.model_fields_set & self.non_nullable if getattr(self, f) is None)
        if bad:
            raise ValueError(f"fields cannot be null: {', '.join(bad)}")
        return self
