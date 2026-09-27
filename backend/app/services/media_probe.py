"""File type sniffing and media validation (magic bytes → decoder/ffprobe)."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.errors import FfmpegMissingError, FileInvalidError, UnsupportedFormatError
from app.models.enums import AssetKind

SNIFF_BYTES = 32
FFPROBE_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class FileType:
    kind: AssetKind
    mime: str
    extension: str
    allowed_extensions: frozenset[str]


JPEG = FileType(AssetKind.IMAGE, "image/jpeg", ".jpg", frozenset({".jpg", ".jpeg"}))
PNG = FileType(AssetKind.IMAGE, "image/png", ".png", frozenset({".png"}))
WEBP = FileType(AssetKind.IMAGE, "image/webp", ".webp", frozenset({".webp"}))
MP4 = FileType(AssetKind.VIDEO, "video/mp4", ".mp4", frozenset({".mp4", ".mov"}))
MOV = FileType(AssetKind.VIDEO, "video/quicktime", ".mov", frozenset({".mov", ".mp4"}))
WAV = FileType(AssetKind.AUDIO, "audio/wav", ".wav", frozenset({".wav"}))
MP3 = FileType(AssetKind.AUDIO, "audio/mpeg", ".mp3", frozenset({".mp3"}))
M4A = FileType(AssetKind.AUDIO, "audio/mp4", ".m4a", frozenset({".m4a"}))

_PIL_FORMATS = {JPEG: "JPEG", PNG: "PNG", WEBP: "WEBP"}


def sniff(head: bytes) -> FileType | None:
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return WEBP
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return WAV
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand == b"qt  ":
            return MOV
        if brand in (b"M4A ", b"M4B "):
            return M4A
        return MP4
    if head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return MP3
    return None


def detect(path: Path, declared_extension: str) -> FileType:
    with path.open("rb") as fh:
        file_type = sniff(fh.read(SNIFF_BYTES))
    if file_type is None:
        raise UnsupportedFormatError(
            "Unsupported file type. Allowed: JPEG, PNG, WEBP, MP4, MOV, WAV, MP3, M4A."
        )
    if declared_extension.lower() not in file_type.allowed_extensions:
        raise UnsupportedFormatError("File extension does not match the file contents.")
    return file_type


@dataclass(frozen=True)
class MediaInfo:
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None


def validate_image(path: Path, file_type: FileType, max_pixels: int) -> MediaInfo:
    expected = _PIL_FORMATS[file_type]
    try:
        with Image.open(path) as img:
            if img.format != expected:
                raise FileInvalidError("Image contents do not match the detected format.")
            width, height = img.size
            if width * height > max_pixels:
                raise FileInvalidError(f"Image is too large ({width}x{height}).")
            img.verify()
        with Image.open(path) as img:
            img.load()  # full decode catches truncated data
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise FileInvalidError("The image could not be decoded.") from exc
    return MediaInfo(width=width, height=height)


def _run_ffprobe(ffprobe: str, path: Path) -> dict[str, object]:
    args = [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell
            args, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FileInvalidError("The media file could not be inspected.") from exc
    if result.returncode != 0:
        raise FileInvalidError("The media file is corrupted or unsupported.")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FileInvalidError("The media file could not be inspected.") from exc
    return data if isinstance(data, dict) else {}


def _to_float(value: object) -> float | None:
    if not isinstance(value, (str, int, float)):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def validate_av(path: Path, file_type: FileType, ffprobe_path: Path | None) -> MediaInfo:
    if ffprobe_path is not None:
        ffprobe = str(ffprobe_path) if ffprobe_path.is_file() else None
    else:
        ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise FfmpegMissingError("FFprobe is required to validate video and audio uploads.")
    data = _run_ffprobe(ffprobe, path)

    raw_streams = data.get("streams")
    streams = [s for s in raw_streams if isinstance(s, dict)] if isinstance(raw_streams, list) else []
    raw_format = data.get("format")
    fmt: dict[str, object] = raw_format if isinstance(raw_format, dict) else {}
    duration = _to_float(fmt.get("duration"))

    if file_type.kind is AssetKind.VIDEO:
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video is None:
            raise FileInvalidError("The video file has no video stream.")
        return MediaInfo(
            width=int(video.get("width") or 0) or None,
            height=int(video.get("height") or 0) or None,
            duration_s=duration,
        )

    if not any(s.get("codec_type") == "audio" for s in streams):
        raise FileInvalidError("The audio file has no audio stream.")
    return MediaInfo(duration_s=duration)
