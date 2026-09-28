"""Filesystem layout under DATA_DIR. All stored paths are relative and generated server-side."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from app.core.errors import AppError
from app.models.enums import AssetKind


class PathOutsideStorageError(AppError):
    status_code = 400
    default_message = "Invalid storage path."


class StorageService:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir.resolve()

    def resolve(self, relative: str) -> Path:
        """Map a stored relative path to an absolute one, refusing anything outside DATA_DIR."""
        rel = PurePosixPath(relative)
        # Reject drive letters / backslashes too: on Windows "C:" would re-anchor the join.
        if (
            rel.is_absolute()
            or not rel.parts
            or any(part in ("..", ".") or ":" in part or "\\" in part for part in rel.parts)
        ):
            raise PathOutsideStorageError()
        candidate = (self.root / Path(*rel.parts)).resolve()
        if not candidate.is_relative_to(self.root):
            raise PathOutsideStorageError()
        return candidate

    def relative(self, absolute: Path) -> str:
        resolved = absolute.resolve()
        if not resolved.is_relative_to(self.root):
            raise PathOutsideStorageError()
        return resolved.relative_to(self.root).as_posix()

    def upload_path(
        self, asset_id: str, kind: AssetKind, extension: str, now: datetime | None = None
    ) -> Path:
        stamp = now or datetime.now(UTC)
        directory = self.root / "uploads" / kind.value / f"{stamp:%Y}" / f"{stamp:%m}"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{asset_id}{extension}"

    def output_path(self, asset_id: str, category: str, extension: str, now: datetime | None = None) -> Path:
        stamp = now or datetime.now(UTC)
        directory = self.root / "outputs" / category / f"{stamp:%Y}" / f"{stamp:%m}"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{asset_id}{extension}"

    def thumbnail_path(self, asset_id: str) -> Path:
        directory = self.root / "thumbnails"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{asset_id}.webp"

    def temp_file(self, suffix: str = ".part") -> Path:
        directory = self.root / "temp"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{uuid.uuid4().hex}{suffix}"

    def move_into_place(self, source: Path, destination: Path) -> None:
        if not destination.resolve().is_relative_to(self.root):
            raise PathOutsideStorageError()
        os.replace(source, destination)

    def delete(self, relative: str) -> None:
        self.resolve(relative).unlink(missing_ok=True)
