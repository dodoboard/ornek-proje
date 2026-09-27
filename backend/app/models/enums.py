from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import Enum


class AssetKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class AssetSource(StrEnum):
    UPLOAD = "upload"
    GENERATED = "generated"
    DERIVED = "derived"


class AssetRole(StrEnum):
    REFERENCE = "reference"
    CANONICAL = "canonical"
    FRONT = "front"
    THREE_QUARTER = "three_quarter"
    FULL_BODY = "full_body"
    PRODUCT_PHOTO = "product_photo"
    CUTOUT = "cutout"
    MASK = "mask"
    PHOTO = "photo"
    FOOTAGE = "footage"
    DRONE = "drone"
    FLOOR_PLAN = "floor_plan"


class ConsentSubject(StrEnum):
    FACE = "face"
    VOICE = "voice"


class PropertyCategory(StrEnum):
    PROPERTY = "property"
    LAND = "land"


class ListingType(StrEnum):
    SALE = "sale"
    RENT = "rent"


class ProjectType(StrEnum):
    SOCIAL = "social"
    PRODUCT_AD = "product_ad"
    REAL_ESTATE = "real_estate"
    LAND = "land"
    CUSTOM = "custom"


def enum_column(enum_cls: type[StrEnum], name: str) -> Enum:
    """Stores enum *values* as VARCHAR with a CHECK constraint (portable to PostgreSQL)."""
    values: Any = lambda cls: [member.value for member in cls]  # noqa: E731
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=values,
        length=32,
    )
