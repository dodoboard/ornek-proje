"""Import every model so `Base.metadata` is complete (Alembic autogenerate relies on this)."""

from app.models.asset import Asset
from app.models.character import Character
from app.models.consent import Consent
from app.models.links import CharacterAsset, ProductAsset, PropertyAsset
from app.models.product import Product
from app.models.project import Project
from app.models.property import Property

__all__ = [
    "Asset",
    "Character",
    "CharacterAsset",
    "Consent",
    "Product",
    "ProductAsset",
    "Project",
    "Property",
    "PropertyAsset",
]
