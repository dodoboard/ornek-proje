"""Encode a sequence of PIL frames to H.264 MP4 with FFmpeg (argv list only, progress, cancellable)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from PIL.Image import Image

from app.core.errors import GenerationFailedError
from app.providers.base import SubprocessRunner
from app.services.ffmpeg.progress import FfmpegProgress


def write_frames(
    frames: Iterable[Image], directory: Path, on_frame: Callable[[int], None] | None = None
) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    count = 0
    for count, frame in enumerate(frames, start=1):
        frame.convert("RGB").save(directory / f"frame_{count:05d}.png", compress_level=1)
        if on_frame:
            on_frame(count)
    return count


def encode_png_sequence(
    ffmpeg: str,
    directory: Path,
    fps: int,
    output: Path,
    run_subprocess: SubprocessRunner,
    on_progress: Callable[[float], None],
    frame_count: int,
    crf: int = 18,
) -> Path:
    """`frame_00001.png …` → MP4 (yuv420p so every player can open it; even dimensions required)."""
    tracker = FfmpegProgress(frame_count / fps, on_progress)
    args = [
        ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error", "-y",
        "-framerate", str(fps), "-i", str(directory / "frame_%05d.png"),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-progress", "pipe:1", str(output),
    ]  # fmt: skip
    result = run_subprocess(args, timeout_s=1800, on_stdout_line=tracker.feed)
    if result.returncode != 0 or not output.is_file():
        raise GenerationFailedError("Video encoding failed (FFmpeg).")
    return output
