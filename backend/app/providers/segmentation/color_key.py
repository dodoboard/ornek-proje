"""Classical (non-AI) background removal for product shots on a plain, uniform background.

The background colour is estimated from the image border; only background-like pixels *connected to
the border* are removed, so white labels or logos inside the product are kept.
"""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

from app.core.config import PerformanceProfile
from app.providers.base import (
    Availability,
    GenerationContext,
    ProviderStatus,
    SegmentationCapabilities,
    SegmentationProvider,
)
from app.providers.device import DeviceInfo

WORK_EDGE = 512


def border_color(image: Image.Image, band: int = 4) -> tuple[int, int, int]:
    w, h = image.size
    band = max(1, min(band, w // 4, h // 4))
    strips = [
        image.crop((0, 0, w, band)),
        image.crop((0, h - band, w, h)),
        image.crop((0, 0, band, h)),
        image.crop((w - band, 0, w, h)),
    ]
    medians = [ImageStat.Stat(s).median for s in strips]
    return tuple(sorted(m[c] for m in medians)[1] for c in range(3))  # type: ignore[return-value]


def color_key_mask(image: Image.Image, tolerance: int = 24) -> Image.Image:
    """Foreground = 255, background (border-connected, within `tolerance` of the border colour) = 0."""
    rgb = image.convert("RGB")
    bg = Image.new("RGB", rgb.size, border_color(rgb))
    diff = ImageChops.difference(rgb, bg)
    channel_max = ImageChops.lighter(ImageChops.lighter(*diff.split()[:2]), diff.split()[2])
    bg_like = channel_max.point(lambda v: 255 if v <= tolerance else 0)

    # Flood from the border on a small copy (pure-Python flood fill), then refine at full size.
    small = bg_like.copy()
    small.thumbnail((WORK_EDGE, WORK_EDGE), Image.Resampling.NEAREST)
    w, h = small.size
    px = small.load()
    assert px is not None
    border = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    for xy in border:
        if px[xy] == 255:
            ImageDraw.floodfill(small, xy, 128, thresh=0)
    outside = small.point(lambda v: 255 if v == 128 else 0).resize(rgb.size, Image.Resampling.NEAREST)
    outside = outside.filter(ImageFilter.MaxFilter(5))  # cover blocky upscaling at the edge
    background = ImageChops.multiply(outside, bg_like)  # only truly background-coloured pixels
    return ImageChops.invert(background)


class ColorKeySegmentationProvider(SegmentationProvider):
    """Deterministic, no model weights. Suitable only for plain studio backgrounds."""

    def availability(self) -> Availability:
        return Availability(ProviderStatus.AVAILABLE, "Classical colour key (plain backgrounds only).")

    def capabilities(self) -> SegmentationCapabilities:
        return SegmentationCapabilities(alpha_matting=False)

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def segment(self, image: Image.Image, ctx: GenerationContext) -> Image.Image:
        tolerance = self.spec.option("tolerance", 24)
        mask = color_key_mask(image, int(tolerance))
        ctx.progress(1.0)
        return mask
