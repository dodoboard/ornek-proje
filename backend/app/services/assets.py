"""Asset ingestion: stream → temp file → sniff/validate → move into place → DB row."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path, PurePath
from typing import BinaryIO

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, FileInvalidError, FileTooLargeError, NotFoundError
from app.core.ids import IdPrefix, new_id
from app.models.asset import Asset
from app.models.consent import Consent
from app.models.enums import AssetKind, AssetSource
from app.models.links import CharacterAsset, ProductAsset, PropertyAsset
from app.services import media_probe
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

CHUNK_BYTES = 1024 * 1024
MB = 1024 * 1024
MAX_FILENAME_CHARS = 255


def kind_limit_bytes(settings: Settings, kind: AssetKind) -> int:
    limits = {
        AssetKind.IMAGE: settings.max_image_upload_mb,
        AssetKind.VIDEO: settings.max_video_upload_mb,
        AssetKind.AUDIO: settings.max_audio_upload_mb,
    }
    return limits[kind] * MB


def max_upload_bytes(settings: Settings) -> int:
    return max(kind_limit_bytes(settings, kind) for kind in AssetKind)


def _safe_display_name(filename: str | None) -> tuple[str | None, str]:
    """Returns (display name kept only as metadata, lower-case extension)."""
    if not filename:
        return None, ""
    name = PurePath(filename.replace("\\", "/")).name  # strip any client-side directories
    name = "".join(ch for ch in name if ch.isprintable())[:MAX_FILENAME_CHARS]
    return name or None, PurePath(name).suffix.lower()


def _stream_to_temp(source: BinaryIO, destination: Path, limit: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with destination.open("wb") as out:
        while chunk := source.read(CHUNK_BYTES):
            size += len(chunk)
            if size > limit:
                raise FileTooLargeError()
            digest.update(chunk)
            out.write(chunk)
    if size == 0:
        raise FileInvalidError("The uploaded file is empty.")
    return size, digest.hexdigest()


def ingest_upload(
    session: Session,
    settings: Settings,
    storage: StorageService,
    source: BinaryIO,
    filename: str | None,
) -> Asset:
    display_name, extension = _safe_display_name(filename)
    temp = storage.temp_file()
    final: Path | None = None
    try:
        size, checksum = _stream_to_temp(source, temp, max_upload_bytes(settings))
        file_type = media_probe.detect(temp, extension)
        if size > kind_limit_bytes(settings, file_type.kind):
            raise FileTooLargeError()

        if file_type.kind is AssetKind.IMAGE:
            info = media_probe.validate_image(temp, file_type, settings.max_image_pixels)
        else:
            info = media_probe.validate_av(temp, file_type, settings.ffprobe_path)

        asset_id = new_id(IdPrefix.ASSET)
        final = storage.upload_path(asset_id, file_type.kind, file_type.extension)
        storage.move_into_place(temp, final)

        asset = Asset(
            id=asset_id,
            kind=file_type.kind,
            source=AssetSource.UPLOAD,
            path=storage.relative(final),
            mime=file_type.mime,
            size_bytes=size,
            checksum_sha256=checksum,
            width=info.width,
            height=info.height,
            duration_s=info.duration_s,
            original_filename=display_name,
            ai_generated=False,
            metadata_json={},
        )
        session.add(asset)
        session.commit()
    except BaseException:
        session.rollback()
        if final is not None:
            final.unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)

    logger.info("asset_ingested", extra={"asset_id": asset.id, "kind": asset.kind.value, "size": size})
    return asset


def get_asset(session: Session, asset_id: str) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError("Asset not found.")
    return asset


def is_referenced(session: Session, asset_id: str) -> bool:
    return bool(
        session.scalar(
            select(
                or_(
                    exists().where(CharacterAsset.asset_id == asset_id),
                    exists().where(ProductAsset.asset_id == asset_id),
                    exists().where(PropertyAsset.asset_id == asset_id),
                    exists().where(Consent.evidence_asset_id == asset_id),
                )
            )
        )
    )


def delete_asset(session: Session, storage: StorageService, asset_id: str) -> None:
    asset = get_asset(session, asset_id)
    if is_referenced(session, asset_id):
        raise ConflictError("The asset is still in use. Detach it first.")
    path = asset.path
    session.delete(asset)
    session.commit()
    storage.delete(path)
