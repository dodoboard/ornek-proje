"""Import every model so `Base.metadata` is complete (Alembic autogenerate relies on this)."""

from app.models.asset import Asset
from app.models.character import Character
from app.models.character_bible import CharacterBible
from app.models.consent import Consent
from app.models.generation import Generation
from app.models.job import Job, Worker
from app.models.links import CharacterAsset, ProductAsset, PropertyAsset
from app.models.product import Product
from app.models.project import Project
from app.models.property import Property
from app.models.script import Script, Shot, Storyboard
from app.models.setting import AppSetting

__all__ = [
    "AppSetting",
    "Asset",
    "Character",
    "CharacterAsset",
    "CharacterBible",
    "Consent",
    "Generation",
    "Job",
    "Product",
    "ProductAsset",
    "Project",
    "Property",
    "PropertyAsset",
    "Script",
    "Shot",
    "Storyboard",
    "Worker",
]
