"""Video providers: Wan (against stubs of the diffusers v0.40.0 API) and the no-AI camera-motion provider.

Encoding uses the real FFmpeg; the Wan model itself is a stub (no GPU here).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.core.config import PerformanceProfile, Settings
from app.core.errors import ProviderUnavailableError
from app.providers.base import GenerationContext, VideoCapabilities, VideoRequest
from app.providers.catalog import ModelSpec
from app.providers.device import DeviceInfo
from app.providers.video.ffmpeg_motion import FfmpegMotionProvider, crop_boxes, render_frames
from app.providers.video.wan_diffusers import T2V_CLASS, WanDiffusersProvider
from app.schemas.video import VideoGenerateRequest
from app.services.image_generation import InvalidGenerationRequestError
from app.services.video_generation import check_video_against_capabilities, frame_count

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg not installed")
CALLS: dict[str, Any] = {}


def _run(
    args: list[str], *, timeout_s: float | None = None, on_stdout_line: Any = None, cwd: Any = None
) -> Any:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s, check=False)
    if on_stdout_line:
        for line in result.stdout.splitlines():
            on_stdout_line(line)
    return result


def _ctx(tmp_path: Path, progress: list[float] | None = None) -> GenerationContext:
    return GenerationContext(tmp_path, (progress.append if progress is not None else lambda _: None), _run)


def _probe(path: Path) -> dict[str, Any]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    data: dict[str, Any] = json.loads(out.stdout)
    return data


# --------------------------------------------------------------------------- stubs (diffusers / torch)


class _Wan:
    vae_scale_factor_spatial = 16
    vae_scale_factor_temporal = 4

    def __init__(self) -> None:
        self.transformer = types.SimpleNamespace(config=types.SimpleNamespace(patch_size=(1, 2, 2)))
        self.vae = types.SimpleNamespace(enable_tiling=lambda: CALLS.__setitem__("tiling", True))

    def enable_model_cpu_offload(self) -> None:
        CALLS["offload"] = True

    def to(self, device: str) -> Any:
        return self

    def __call__(self, **kwargs: Any) -> Any:
        CALLS.setdefault("calls", []).append((type(self).__name__, kwargs))
        for step in range(kwargs["num_inference_steps"]):
            kwargs["callback_on_step_end"](self, step, 0, {})
        w, h = kwargs["width"], kwargs["height"]
        frames = [Image.new("RGB", (w, h), (i * 40 % 255, 80, 160)) for i in range(kwargs["num_frames"])]
        return types.SimpleNamespace(frames=[frames])


class WanPipeline(_Wan):
    pass


class WanImageToVideoPipeline(_Wan):
    @classmethod
    def from_pipe(cls, pipe: Any) -> WanImageToVideoPipeline:
        CALLS["from_pipe"] = CALLS.get("from_pipe", 0) + 1
        return cls()


class _DiffusionPipeline:
    @staticmethod
    def from_pretrained(source: str, **kwargs: Any) -> Any:
        CALLS["from_pretrained"] = {"source": source, **kwargs}
        return CALLS.get("loaded_cls", WanPipeline)()


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    CALLS.clear()
    diffusers = types.ModuleType("diffusers")
    diffusers.DiffusionPipeline = _DiffusionPipeline  # type: ignore[attr-defined]
    diffusers.WanPipeline = WanPipeline  # type: ignore[attr-defined]
    diffusers.WanImageToVideoPipeline = WanImageToVideoPipeline  # type: ignore[attr-defined]
    torch = types.ModuleType("torch")
    torch.bfloat16 = "bf16"  # type: ignore[attr-defined]
    torch.Generator = lambda device: types.SimpleNamespace(manual_seed=lambda s: ("gen", s))  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "diffusers", diffusers)
    monkeypatch.setitem(sys.modules, "torch", torch)
    return CALLS


def _wan(settings: Settings) -> WanDiffusersProvider:
    spec = ModelSpec(
        provider="wan_diffusers", repo_id="Wan-AI/Wan2.2-TI2V-5B-Diffusers", fps=[24], max_frames=121
    )
    return WanDiffusersProvider("wan22_ti2v_5b", spec, settings)


CUDA = DeviceInfo(device="cuda", dtype="bfloat16")


@needs_ffmpeg
def test_wan_text_and_image_to_video(settings: Settings, stubs: dict[str, Any], tmp_path: Path) -> None:
    provider = _wan(settings)
    provider.load(CUDA, PerformanceProfile.BALANCED)
    assert stubs["from_pretrained"]["torch_dtype"] == "bf16"
    assert stubs["offload"] and stubs["tiling"]  # VAE tiling protects the 16 GB decode peak
    caps = provider.capabilities()
    assert (caps.size_multiple, caps.frame_step) == (32, 4)

    progress: list[float] = []
    out = provider.generate(
        VideoRequest(prompt="a woman on a beach", width=64, height=96, num_frames=9, fps=24, steps=3, seed=7,
                     motion="slow_push_in"),
        tmp_path / "t2v.mp4", _ctx(tmp_path, progress),
    )  # fmt: skip
    cls, kwargs = stubs["calls"][-1]
    assert cls == T2V_CLASS and "image" not in kwargs
    assert kwargs["prompt"].endswith("slow camera push-in") and kwargs["output_type"] == "pil"
    assert kwargs["guidance_scale"] == 5.0 and kwargs["negative_prompt"]
    stream = _probe(out)["streams"][0]
    assert (stream["width"], stream["height"], int(stream["nb_frames"])) == (64, 96, 9)
    assert progress[-1] == pytest.approx(1.0) and progress == sorted(progress)

    still = tmp_path / "first.png"
    Image.new("RGB", (200, 100), "red").save(still)
    provider.generate(
        VideoRequest(prompt="x", width=64, height=96, num_frames=5, fps=24, steps=1, seed=1, image=still),
        tmp_path / "i2v.mp4", _ctx(tmp_path / "i2v"),
    )  # fmt: skip
    cls, kwargs = stubs["calls"][-1]
    assert cls == "WanImageToVideoPipeline" and kwargs["image"].size == (64, 96)
    provider.generate(
        VideoRequest(prompt="x", width=64, height=96, num_frames=5, fps=24, steps=1, seed=1, image=still),
        tmp_path / "i2v2.mp4", _ctx(tmp_path / "i2v2"),
    )  # fmt: skip
    assert stubs["from_pipe"] == 1  # the I2V pipeline shares the loaded weights and is cached


def test_wan_rejects_foreign_pipeline(settings: Settings, stubs: dict[str, Any]) -> None:
    stubs["loaded_cls"] = type("FluxPipeline", (), {})
    with pytest.raises(ProviderUnavailableError, match="expected a Wan pipeline"):
        _wan(settings).load(CUDA, PerformanceProfile.BALANCED)


# --------------------------------------------------------------------------- camera motion (no AI)


def test_crop_boxes_move_smoothly_inside_the_image() -> None:
    boxes = list(crop_boxes((1600, 900), (704, 1280), "slow_push_in", 25))
    widths = [b[2] - b[0] for b in boxes]
    assert widths == sorted(widths, reverse=True) and widths[-1] < widths[0]
    for motion in ("pan_left", "pan_right", "tilt_up", "tilt_down", "orbit", "handheld"):
        for left, top, right, bottom in crop_boxes((1600, 900), (1280, 720), motion, 30):
            assert left >= 0 and top >= 0 and right <= 1600 + 1e-6 and bottom <= 900 + 1e-6
    lefts = [b[0] for b in crop_boxes((1600, 900), (1280, 720), "pan_right", 20)]
    assert lefts == sorted(lefts) and lefts[-1] > lefts[0]
    static = list(crop_boxes((1600, 900), (1280, 720), "static", 5))
    assert len(set(static)) == 1


def test_static_motion_keeps_pixels() -> None:
    img = Image.effect_noise((320, 180), 60).convert("RGB")
    frames = list(render_frames(img, (320, 180), "static", 3))
    assert frames[0].tobytes() == img.tobytes()


@needs_ffmpeg
def test_camera_motion_provider_encodes_clip(settings: Settings, tmp_path: Path) -> None:
    provider = FfmpegMotionProvider("camera_motion", ModelSpec(provider="ffmpeg_motion"), settings)
    assert provider.capabilities().uses_ai is False
    still = tmp_path / "photo.png"
    Image.effect_noise((400, 300), 50).convert("RGB").save(still)
    out = provider.generate(
        VideoRequest(prompt="", width=160, height=90, num_frames=30, fps=30, steps=1, seed=0, image=still,
                     motion="pan_right"),
        tmp_path / "clip.mp4", _ctx(tmp_path),
    )  # fmt: skip
    info = _probe(out)
    assert info["streams"][0]["codec_name"] == "h264" and int(info["streams"][0]["nb_frames"]) == 30
    assert float(info["format"]["duration"]) == pytest.approx(1.0, abs=0.05)


# --------------------------------------------------------------------------- request validation


WAN_CAPS = VideoCapabilities(
    text_to_video=True, negative_prompt=True, guidance=True, fps=(24,), max_frames=121, frame_step=4,
    size_multiple=32, max_size=1280,
)  # fmt: skip


def test_frame_count_snaps_to_model_grid() -> None:
    assert frame_count(5, 24, WAN_CAPS) == 121
    assert frame_count(2, 24, WAN_CAPS) == 49
    assert frame_count(20, 24, WAN_CAPS) == 121
    assert frame_count(1.5, 30, VideoCapabilities(max_frames=600)) == 45


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"prompt": "", "width": 704, "height": 1280}, "Describe"),
        ({"prompt": "x", "width": 700, "height": 1280}, "multiple of 32"),
        ({"prompt": "x", "fps": 30}, "Supported frame rates"),
        ({"prompt": "x", "duration_s": 12}, "At most 121 frames"),
        ({"prompt": "x", "image_asset_id": "A", "last_image_asset_id": "B"}, "last-frame"),
    ],
)
def test_video_request_validation(body: dict[str, Any], message: str) -> None:
    with pytest.raises(InvalidGenerationRequestError, match=message):
        check_video_against_capabilities(VideoGenerateRequest.model_validate(body), WAN_CAPS)


def test_image_only_models_need_an_image() -> None:
    caps = VideoCapabilities(text_to_video=False, uses_ai=False, fps=(24,), size_multiple=2, max_size=3840)
    with pytest.raises(InvalidGenerationRequestError, match="needs a start image"):
        check_video_against_capabilities(VideoGenerateRequest(width=704, height=1280), caps)
    assert check_video_against_capabilities(VideoGenerateRequest(image_asset_id="A"), caps) == 24
