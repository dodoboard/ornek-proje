from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import UnsupportedFormatError
from app.models.enums import AssetKind
from app.services import media_probe
from app.services.assets import _safe_display_name
from app.services.storage import PathOutsideStorageError, StorageService


@pytest.mark.parametrize(
    "bad", ["../x", "/etc/passwd", "uploads/../../x", "", "C:/Windows/x", "uploads\\..\\x"]
)
def test_storage_resolve_rejects_escape(tmp_path: Path, bad: str) -> None:
    with pytest.raises(PathOutsideStorageError):
        StorageService(tmp_path).resolve(bad)


def test_storage_upload_path_is_inside_root(tmp_path: Path) -> None:
    storage = StorageService(tmp_path)
    path = storage.upload_path("AST_X", AssetKind.IMAGE, ".png")
    assert path.parent.is_dir()
    assert storage.resolve(storage.relative(path)) == path.resolve()


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"\xff\xd8\xff\xe0" + b"\0" * 28, media_probe.JPEG),
        (b"\x89PNG\r\n\x1a\n" + b"\0" * 24, media_probe.PNG),
        (b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 16, media_probe.WEBP),
        (b"RIFF\0\0\0\0WAVEfmt " + b"\0" * 16, media_probe.WAV),
        (b"\0\0\0\x18ftypqt  " + b"\0" * 20, media_probe.MOV),
        (b"\0\0\0\x18ftypisom" + b"\0" * 20, media_probe.MP4),
        (b"\0\0\0\x18ftypM4A " + b"\0" * 20, media_probe.M4A),
        (b"ID3\x04" + b"\0" * 28, media_probe.MP3),
        (b"<svg" + b"\0" * 28, None),
        (b"GIF89a" + b"\0" * 26, None),
    ],
)
def test_sniff(head: bytes, expected: media_probe.FileType | None) -> None:
    assert media_probe.sniff(head) == expected


def test_detect_requires_matching_extension(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 24)
    assert media_probe.detect(path, ".png") is media_probe.PNG
    with pytest.raises(UnsupportedFormatError):
        media_probe.detect(path, ".jpg")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("C:\\Users\\me\\Desktop\\photo.JPG", ("photo.JPG", ".jpg")),
        ("../../etc/passwd", ("passwd", "")),
        ("a\x00b\n.png", ("ab.png", ".png")),
        (None, (None, "")),
    ],
)
def test_safe_display_name(raw: str | None, expected: tuple[str | None, str]) -> None:
    assert _safe_display_name(raw) == expected
