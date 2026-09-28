from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.core.config import PerformanceProfile, Settings
from app.providers.base import GenerationContext, ImageRequest, VideoRequest
from app.providers.catalog import ModelSpec
from app.providers.device import DeviceInfo
from app.providers.image.fake import FakeImageProvider
from app.providers.video.fake import FakeVideoProvider
from tests.conftest import requires_ffmpeg


def _ctx(tmp_path: Path, progress: list[float]) -> GenerationContext:
    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        on_line = kwargs.get("on_stdout_line")
        result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=120)
        if callable(on_line):
            for line in result.stdout.splitlines():
                on_line(line)
        return result

    return GenerationContext(temp_dir=tmp_path, progress=progress.append, run_subprocess=run)


def test_fake_image_is_labelled_and_deterministic(settings: Settings, tmp_path: Path) -> None:
    provider = FakeImageProvider("dev_fake_image", ModelSpec(provider="dev_fake_image"), settings)
    provider.load(DeviceInfo(device="cpu", dtype="float32"), PerformanceProfile.BALANCED)
    progress: list[float] = []
    request = ImageRequest(prompt="perfume on marble", width=128, height=96, steps=3, seed=7, num_images=2)
    first = provider.generate(request, _ctx(tmp_path, progress))
    again = provider.generate(request, _ctx(tmp_path, []))
    assert [im.size for im in first] == [(128, 96), (128, 96)]
    assert first[0].tobytes() == again[0].tobytes()
    assert first[0].tobytes() != first[1].tobytes()
    assert progress[-1] == 1.0


def test_fake_image_honours_cancellation(settings: Settings, tmp_path: Path) -> None:
    provider = FakeImageProvider("dev_fake_image", ModelSpec(provider="dev_fake_image"), settings)

    class Stop(Exception):
        pass

    def cancel(_: float) -> None:
        raise Stop

    ctx = GenerationContext(temp_dir=tmp_path, progress=cancel, run_subprocess=subprocess.run)  # type: ignore[arg-type]
    with pytest.raises(Stop):
        provider.generate(ImageRequest(prompt="x", width=64, height=64, steps=5, seed=0), ctx)


@requires_ffmpeg
def test_fake_video_writes_mp4(settings: Settings, tmp_path: Path) -> None:
    provider = FakeVideoProvider("dev_fake_video", ModelSpec(provider="dev_fake_video"), settings)
    progress: list[float] = []
    out = tmp_path / "clip.mp4"
    request = VideoRequest(prompt="villa", width=160, height=96, num_frames=24, fps=24, steps=1, seed=1)
    provider.generate(request, out, _ctx(tmp_path, progress))
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,nb_read_frames", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert probe.stdout.strip() == "160,96,24"
    assert progress and progress[-1] == 1.0
