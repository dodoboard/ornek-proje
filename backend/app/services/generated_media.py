"""Persist generated media with AI-disclosure metadata, optional visible label and thumbnails."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
from sqlalchemy.orm import Session

from app.core.errors import UnsupportedFormatError
from app.core.ids import IdPrefix, new_id
from app.models.asset import Asset
from app.models.enums import AssetKind, AssetSource
from app.services.storage import StorageService

THUMBNAIL_EDGE = 512
WATERMARK_TEXT = "AI generated"
DISCLOSURE_PNG_KEY = "ai_disclosure"


def apply_watermark(image: Image.Image, text: str = WATERMARK_TEXT) -> Image.Image:
    """Small, legible label in the bottom-right corner (does not cover the subject)."""
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    size = max(12, base.width // 40)
    font = ImageFont.load_default(size=size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    pad = size // 2
    w, h = right - left + 2 * pad, bottom - top + 2 * pad
    x, y = base.width - w - pad, base.height - h - pad
    draw.rounded_rectangle((x, y, x + w, y + h), radius=pad, fill=(0, 0, 0, 140))
    draw.text((x + pad - left, y + pad - top), text, font=font, fill=(255, 255, 255, 230))
    return Image.alpha_composite(base, overlay).convert("RGB")


def write_thumbnail(image: Image.Image, path: Path) -> None:
    thumb = image.convert("RGB")
    thumb.thumbnail((THUMBNAIL_EDGE, THUMBNAIL_EDGE))
    thumb.save(path, format="WEBP", quality=82)


def store_generated_image(
    session: Session,
    storage: StorageService,
    image: Image.Image,
    disclosure: dict[str, Any],
    *,
    watermark: bool,
) -> Asset:
    """Write a PNG (with disclosure tEXt chunk) + thumbnail and add an Asset row (caller commits)."""
    asset_id = new_id(IdPrefix.ASSET)
    final = apply_watermark(image) if watermark else image.convert("RGB")
    metadata = {**disclosure, "watermark": watermark}

    info = PngInfo()
    info.add_text(DISCLOSURE_PNG_KEY, json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    info.add_text("Software", "AI Influencer Studio (local)")

    path = storage.output_path(asset_id, "images", ".png")
    final.save(path, format="PNG", pnginfo=info)
    write_thumbnail(final, storage.thumbnail_path(asset_id))

    data = path.read_bytes()
    asset = Asset(
        id=asset_id,
        kind=AssetKind.IMAGE,
        source=AssetSource.GENERATED,
        path=storage.relative(path),
        mime="image/png",
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        width=final.width,
        height=final.height,
        duration_s=None,
        original_filename=None,
        ai_generated=True,
        metadata_json=metadata,
    )
    session.add(asset)
    return asset


def ensure_thumbnail(storage: StorageService, asset: Asset) -> Path:
    """Create the thumbnail on first request (uploads get one lazily)."""
    if asset.kind is not AssetKind.IMAGE:
        raise UnsupportedFormatError("Thumbnails are only available for images.")
    path = storage.thumbnail_path(asset.id)
    if not path.is_file():
        with Image.open(storage.resolve(asset.path)) as img:
            write_thumbnail(img, path)
    return path


def delete_media_files(storage: StorageService, assets: list[Asset]) -> None:
    for asset in assets:
        storage.delete(asset.path)
        storage.thumbnail_path(asset.id).unlink(missing_ok=True)
