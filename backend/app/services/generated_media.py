"""Persist generated media with AI-disclosure metadata, optional visible label and thumbnails."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
from sqlalchemy.orm import Session

from app.core.errors import GenerationFailedError, UnsupportedFormatError
from app.core.ids import IdPrefix, new_id
from app.models.asset import Asset
from app.models.enums import AssetKind, AssetSource
from app.providers.base import SubprocessRunner
from app.services.storage import StorageService

THUMBNAIL_EDGE = 512
WATERMARK_TEXT = "AI generated"
DISCLOSURE_PNG_KEY = "ai_disclosure"


def _label_box(
    size: tuple[int, int], text: str, corner: str
) -> tuple[
    ImageFont.FreeTypeFont | ImageFont.ImageFont, tuple[int, int, int, int], tuple[int, int, int, int], int
]:
    width, height = size
    font_size = max(12, width // 40)
    font = ImageFont.load_default(size=font_size)
    left, top, right, bottom = (
        round(v) for v in ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font)
    )
    pad = font_size // 2
    w, h = right - left + 2 * pad, bottom - top + 2 * pad
    x = width - w - pad if corner.endswith("right") else pad
    y = height - h - pad if corner.startswith("bottom") else pad
    return font, (x, y, x + w, y + h), (left, top, right, bottom), pad


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def apply_watermark(
    image: Image.Image, text: str = WATERMARK_TEXT, avoid: tuple[int, int, int, int] | None = None
) -> Image.Image:
    """Small, legible label in a corner (bottom-right by default); `avoid` keeps it off e.g. a product."""
    base = image.convert("RGBA")
    corners = ("bottom-right", "bottom-left", "top-right", "top-left")
    choice = corners[0]
    if avoid is not None:
        choice = next(
            (c for c in corners if not _overlaps(_label_box(base.size, text, c)[1], avoid)), corners[0]
        )
    font, (x0, y0, x1, y1), (left, top, _, _), pad = _label_box(base.size, text, choice)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=pad, fill=(0, 0, 0, 140))
    draw.text((x0 + pad - left, y0 + pad - top), text, font=font, fill=(255, 255, 255, 230))
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
    ai_generated: bool = True,
) -> Asset:
    """Write a PNG (with disclosure tEXt chunk) + thumbnail and add an Asset row (caller commits)."""
    asset_id = new_id(IdPrefix.ASSET)
    final = apply_watermark(image) if watermark else image.convert("RGB")
    metadata = {"watermark": watermark, **disclosure}

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
        ai_generated=ai_generated,
        metadata_json=metadata,
    )
    session.add(asset)
    return asset


def store_derived_image(
    session: Session, storage: StorageService, image: Image.Image, metadata: dict[str, Any]
) -> Asset:
    """Lossless PNG (alpha kept) derived from existing pixels, e.g. a product cutout or mask."""
    asset_id = new_id(IdPrefix.ASSET)
    path = storage.output_path(asset_id, "derived", ".png")
    image.save(path, format="PNG")
    write_thumbnail(image, storage.thumbnail_path(asset_id))
    data = path.read_bytes()
    asset = Asset(
        id=asset_id,
        kind=AssetKind.IMAGE,
        source=AssetSource.DERIVED,
        path=storage.relative(path),
        mime="image/png",
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        width=image.width,
        height=image.height,
        duration_s=None,
        original_filename=None,
        ai_generated=False,
        metadata_json=metadata,
    )
    session.add(asset)
    return asset


def store_generated_video(
    session: Session,
    storage: StorageService,
    source: Path,
    disclosure: dict[str, Any],
    *,
    ffmpeg: str,
    ffprobe_path: Path | None,
    run: SubprocessRunner,
    temp_dir: Path,
    ai_generated: bool = True,
) -> Asset:
    """Copy (no re-encode) into outputs with the disclosure in the MP4 `comment` tag, plus a thumbnail."""
    from app.services.media_probe import MP4, validate_av

    asset_id = new_id(IdPrefix.ASSET)
    path = storage.output_path(asset_id, "videos", ".mp4")
    comment = json.dumps(disclosure, ensure_ascii=False, sort_keys=True)
    remux = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-map", "0", "-c", "copy",
        "-metadata", f"comment={comment}", "-movflags", "+faststart", str(path),
    ]  # fmt: skip
    if run(remux, timeout_s=300).returncode != 0 or not path.is_file():
        raise GenerationFailedError("Could not write the video file.")
    still = temp_dir / f"{asset_id}_thumb.png"
    grab = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-frames:v", "1", str(still)]
    if run(grab, timeout_s=120).returncode == 0 and still.is_file():
        with Image.open(still) as frame:
            write_thumbnail(frame, storage.thumbnail_path(asset_id))
    info = validate_av(path, MP4, ffprobe_path)
    data = path.read_bytes()
    asset = Asset(
        id=asset_id,
        kind=AssetKind.VIDEO,
        source=AssetSource.GENERATED,
        path=storage.relative(path),
        mime="video/mp4",
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        width=info.width,
        height=info.height,
        duration_s=info.duration_s,
        original_filename=None,
        ai_generated=ai_generated,
        metadata_json=disclosure,
    )
    session.add(asset)
    return asset


def ensure_thumbnail(storage: StorageService, asset: Asset) -> Path:
    """Create the thumbnail on first request (uploads get one lazily)."""
    path = storage.thumbnail_path(asset.id)
    if asset.kind is AssetKind.VIDEO and path.is_file():
        return path  # written when the video was generated
    if asset.kind is not AssetKind.IMAGE:
        raise UnsupportedFormatError("Thumbnails are only available for images and generated videos.")
    if not path.is_file():
        with Image.open(storage.resolve(asset.path)) as img:
            write_thumbnail(img, path)
    return path


def delete_media_files(storage: StorageService, assets: list[Asset]) -> None:
    for asset in assets:
        storage.delete(asset.path)
        storage.thumbnail_path(asset.id).unlink(missing_ok=True)
