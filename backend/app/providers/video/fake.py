"""DEV/TEST ONLY placeholder video provider: slow zoom over the input (or a placeholder) image via FFmpeg."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.core.config import PerformanceProfile
from app.core.errors import FfmpegMissingError, GenerationFailedError
from app.providers.base import (
    Availability,
    GenerationContext,
    Maturity,
    ProviderStatus,
    VideoCapabilities,
    VideoGenerationProvider,
    VideoRequest,
)
from app.providers.device import DeviceInfo
from app.providers.image.fake import render_placeholder
from app.services.ffmpeg.binary import resolve_binary
from app.services.ffmpeg.progress import FfmpegProgress


class FakeVideoProvider(VideoGenerationProvider):
    maturity = Maturity.DEV_ONLY
    heavy = False

    def availability(self) -> Availability:
        if resolve_binary("ffmpeg", self.settings.ffmpeg_path) is None:
            return Availability(ProviderStatus.NOT_INSTALLED, "FFmpeg is required for the placeholder video.")
        return Availability(ProviderStatus.AVAILABLE, "Development placeholder; zooms over a still image.")

    def capabilities(self) -> VideoCapabilities:
        return VideoCapabilities(
            image_to_video=True, text_to_video=True, negative_prompt=False, guidance=False,
            fps=(24, 25, 30), max_frames=241, size_multiple=2, default_steps=1,
        )  # fmt: skip

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate(self, request: VideoRequest, output: Path, ctx: GenerationContext) -> Path:
        ffmpeg = resolve_binary("ffmpeg", self.settings.ffmpeg_path)
        if ffmpeg is None:
            raise FfmpegMissingError()
        still = ctx.temp_dir / "placeholder_still.png"
        if request.image is not None:
            with Image.open(request.image) as src:
                src.convert("RGB").resize((request.width, request.height)).save(still)
        else:
            render_placeholder(request.width, request.height, request.seed, request.prompt).save(still)

        duration = request.num_frames / request.fps
        zoom = (
            f"scale={request.width * 2}:{request.height * 2},"
            f"zoompan=z='min(zoom+0.0015,1.3)':d={request.num_frames}:s={request.width}x{request.height}"
            f":fps={request.fps}"
        )
        tracker = FfmpegProgress(duration, ctx.progress)
        args = [
            ffmpeg, "-hide_banner", "-nostats", "-loglevel", "error", "-y",
            "-loop", "1", "-i", str(still), "-vf", zoom, "-frames:v", str(request.num_frames),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-progress", "pipe:1", str(output),
        ]  # fmt: skip
        result = ctx.run_subprocess(args, timeout_s=600, on_stdout_line=tracker.feed)
        if result.returncode != 0 or not output.is_file():
            raise GenerationFailedError("Placeholder video encode failed.")
        return output
