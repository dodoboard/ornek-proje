"""Attach/detach assets to characters, products and properties with role/kind rules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnsupportedFormatError
from app.models.character import Character
from app.models.enums import AssetKind, AssetRole, ConsentSubject
from app.models.links import CharacterAsset, ProductAsset, PropertyAsset
from app.models.product import Product
from app.models.property import Property
from app.schemas.asset import AssetLinkCreate
from app.services.assets import get_asset
from app.services.consents import require_active_consent

IMAGE = frozenset({AssetKind.IMAGE})
IMAGE_OR_VIDEO = frozenset({AssetKind.IMAGE, AssetKind.VIDEO})
VIDEO = frozenset({AssetKind.VIDEO})

CHARACTER_ROLES: dict[AssetRole, frozenset[AssetKind]] = {
    AssetRole.REFERENCE: IMAGE,
    AssetRole.CANONICAL: IMAGE,
    AssetRole.FRONT: IMAGE,
    AssetRole.THREE_QUARTER: IMAGE,
    AssetRole.FULL_BODY: IMAGE,
}
PRODUCT_ROLES: dict[AssetRole, frozenset[AssetKind]] = {
    AssetRole.PRODUCT_PHOTO: IMAGE,
    AssetRole.CUTOUT: IMAGE,
    AssetRole.MASK: IMAGE,
    AssetRole.REFERENCE: IMAGE,
}
PROPERTY_ROLES: dict[AssetRole, frozenset[AssetKind]] = {
    AssetRole.PHOTO: IMAGE,
    AssetRole.FOOTAGE: VIDEO,
    AssetRole.DRONE: IMAGE_OR_VIDEO,
    AssetRole.FLOOR_PLAN: IMAGE,
}

type Link = CharacterAsset | ProductAsset | PropertyAsset


def _check_role(roles: dict[AssetRole, frozenset[AssetKind]], role: AssetRole, kind: AssetKind) -> None:
    allowed = roles.get(role)
    if allowed is None:
        raise UnsupportedFormatError(f"Role '{role.value}' is not valid here.")
    if kind not in allowed:
        raise UnsupportedFormatError(
            f"Role '{role.value}' requires {', '.join(sorted(k.value for k in allowed))}."
        )


def _ensure_new(session: Session, link: Link, owner_column: str) -> None:
    link_cls = type(link)
    stmt = select(link_cls).where(
        getattr(link_cls, owner_column) == getattr(link, owner_column),
        link_cls.asset_id == link.asset_id,
        link_cls.role == link.role,
    )
    if session.scalar(stmt) is not None:
        raise ConflictError("This asset is already attached with that role.")


def attach_to_character(session: Session, character: Character, payload: AssetLinkCreate) -> Character:
    asset = get_asset(session, payload.asset_id)
    _check_role(CHARACTER_ROLES, payload.role, asset.kind)
    if character.is_real_person:
        require_active_consent(session, character.consent_id, ConsentSubject.FACE)
    link = CharacterAsset(character_id=character.id, **payload.model_dump())
    _ensure_new(session, link, "character_id")
    character.assets.append(link)
    session.commit()
    return character


def attach_to_product(session: Session, product: Product, payload: AssetLinkCreate) -> Product:
    asset = get_asset(session, payload.asset_id)
    _check_role(PRODUCT_ROLES, payload.role, asset.kind)
    link = ProductAsset(product_id=product.id, **payload.model_dump())
    _ensure_new(session, link, "product_id")
    product.assets.append(link)
    session.commit()
    return product


def attach_to_property(session: Session, prop: Property, payload: AssetLinkCreate) -> Property:
    asset = get_asset(session, payload.asset_id)
    _check_role(PROPERTY_ROLES, payload.role, asset.kind)
    link = PropertyAsset(property_id=prop.id, **payload.model_dump())
    _ensure_new(session, link, "property_id")
    prop.assets.append(link)
    session.commit()
    return prop


def detach(session: Session, link_cls: type[Link], owner_column: str, owner_id: str, asset_id: str) -> None:
    stmt = select(link_cls).where(getattr(link_cls, owner_column) == owner_id, link_cls.asset_id == asset_id)
    links = list(session.scalars(stmt))
    if not links:
        raise NotFoundError("Asset is not attached.")
    for link in links:
        session.delete(link)
    session.commit()
