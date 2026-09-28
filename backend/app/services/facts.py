"""Verified facts of a project (product / property / character / brief) as {{placeholder}} values.

Only non-empty, user-provided values are included. Scripts reference them as `{{key}}`; the value is
filled in by the server, never typed by the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.product import Product
from app.models.project import Project
from app.models.property import Property

PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z0-9_.]+)\s*\}\}")

_YES_NO = {"tr": ("var", "yok"), "en": ("yes", "no")}


def format_number(value: float | Decimal, language: str) -> str:
    number = Decimal(str(value)).normalize()
    text = f"{number:,f}" if number == number.to_integral() else f"{number:,.2f}"
    if language.startswith("tr"):  # 1.250.000,50
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


def format_price(value: Decimal, currency: str, language: str) -> str:
    return f"{format_number(value, language)} {currency}"


@dataclass
class FactSheet:
    language: str
    values: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    #: Extra user-provided text (brief, product description) whose wording counts as verified.
    verified_text: list[str] = field(default_factory=list)

    def add(self, key: str, value: object, label: str) -> None:
        if value is None:
            return
        text = str(value).strip()
        if text:
            self.values[key] = text
            self.labels[key] = label

    def render(self, text: str) -> tuple[str, list[str]]:
        """Replace {{key}} with verified values; returns (text, unknown keys)."""
        unknown: list[str] = []

        def swap(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in self.values:
                return self.values[key]
            unknown.append(key)
            return match.group(0)

        return PLACEHOLDER_RE.sub(swap, text), unknown

    def prompt_lines(self) -> str:
        if not self.values:
            return "(no verified facts were provided)"
        return "\n".join(f"- {{{{{k}}}}} = {v}   ({self.labels[k]})" for k, v in self.values.items())


def collect_facts(session: Session, project: Project, brief: str = "") -> FactSheet:
    language = project.settings.get("language", "tr") if isinstance(project.settings, dict) else "tr"
    sheet = FactSheet(language=language)
    yes, no = _YES_NO["tr" if language.startswith("tr") else "en"]

    if project.character_id and (character := session.get(Character, project.character_id)):
        sheet.add("character.name", character.name, "presenter's name")

    if project.product_id and (product := session.get(Product, project.product_id)):
        sheet.add("product.name", product.name, "product name")
        sheet.add("product.brand", product.brand, "brand")
        if product.price is not None and product.currency:
            sheet.add("product.price", format_price(product.price, product.currency, language), "price")
        sheet.add("product.cta", product.cta, "call to action")
        sheet.add("product.website", product.website, "website")
        for i, feature in enumerate(product.features, start=1):
            sheet.add(f"product.feature_{i}", feature, "verified feature")
        sheet.verified_text += [product.description, *product.features]

    if project.property_id and (prop := session.get(Property, project.property_id)):
        sheet.add("property.title", prop.title, "listing title")
        sheet.add("property.type", prop.property_type, "property type")
        sheet.add(
            "property.listing_type", prop.listing_type.value if prop.listing_type else None, "sale/rent"
        )
        if prop.price is not None and prop.currency:
            sheet.add("property.price", format_price(prop.price, prop.currency, language), "price")
        sheet.add("property.location", prop.location, "location")
        if prop.square_meters is not None:
            sheet.add("property.sqm", f"{format_number(prop.square_meters, language)} m²", "floor area")
        if prop.land_square_meters is not None:
            sheet.add(
                "property.land_sqm", f"{format_number(prop.land_square_meters, language)} m²", "land area"
            )
        sheet.add("property.rooms", prop.rooms, "rooms")
        sheet.add("property.bathrooms", prop.bathrooms, "bathrooms")
        sheet.add("property.floors", prop.floors, "floors")
        sheet.add("property.building_age", prop.building_age, "building age (years)")
        sheet.add("property.zoning", prop.zoning, "zoning status")
        sheet.add("property.parcel", prop.parcel_info, "parcel information")
        for key, value, label in (
            ("property.road_access", prop.road_access, "road access"),
            ("property.electricity", prop.electricity, "electricity"),
            ("property.water", prop.water, "water"),
        ):
            if value is not None:
                sheet.add(key, yes if value else no, label)
        sheet.add("property.contact", prop.contact, "contact")
        sheet.add("property.website", prop.website, "website")
        for i, feature in enumerate(prop.features, start=1):
            sheet.add(f"property.feature_{i}", feature, "verified feature")
        sheet.verified_text += [prop.description, *prop.features]

    if brief:
        sheet.verified_text.append(brief)
    return sheet
