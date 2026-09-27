"""Product compositing that keeps the product's original pixels (logos, labels, text).

Pipeline: cutout (original RGB + segmentation alpha) → placement (translate, optional uniform scale)
→ optional contact shadow on the background → alpha composite → optional AI edge harmonisation in a
thin ring around the silhouette → preservation report comparing the protected product pixels.
Everything here is pure Pillow so it is deterministic and unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ALPHA_FLOOR = 8  # alpha below this counts as background when cropping
#: Matting models rarely output exactly 255 inside the object; near-opaque alpha is snapped to 255 so
#: the product interior is shown (and protected) with its exact original pixels.
ALPHA_SOLID = 240


def make_cutout(photo: Image.Image, mask: Image.Image) -> Image.Image:
    """RGBA with the photo's exact RGB and the mask as alpha, cropped to the product's bounding box."""
    rgb = photo.convert("RGB")
    alpha = mask.convert("L")
    if alpha.size != rgb.size:
        alpha = alpha.resize(rgb.size, Image.Resampling.BILINEAR)
    alpha = alpha.point(lambda v: 255 if v >= ALPHA_SOLID else (0 if v < ALPHA_FLOOR else v))
    box = alpha.getbbox()
    if box is None:
        raise ValueError("The segmentation mask is empty: no product was found.")
    rgba = rgb.copy()
    rgba.putalpha(alpha)
    return rgba.crop(box)


@dataclass(frozen=True)
class Placement:
    """`x`: horizontal centre (0..1); `y`: bottom edge of the product (0..1); `height_ratio`: product
    height / canvas height. `native_scale` ignores `height_ratio` and keeps the cutout's pixel size."""

    x: float = 0.5
    y: float = 0.85
    height_ratio: float = 0.5
    native_scale: bool = False


@dataclass(frozen=True)
class PlacedProduct:
    layer: Image.Image  # RGBA, canvas size, transparent outside the product
    box: tuple[int, int, int, int]
    scale: float
    clamped: bool


def place(cutout: Image.Image, canvas_size: tuple[int, int], placement: Placement) -> PlacedProduct:
    cw, ch = canvas_size
    if placement.native_scale:
        size = cutout.size
    else:
        target_h = max(1, round(placement.height_ratio * ch))
        size = (max(1, round(cutout.width * target_h / cutout.height)), target_h)
    if size[0] > cw or size[1] > ch:
        raise ValueError(
            f"The product ({size[0]}x{size[1]}px) does not fit the {cw}x{ch}px canvas; lower its size."
        )
    scale = size[1] / cutout.height
    product = cutout if size == cutout.size else cutout.resize(size, Image.Resampling.LANCZOS)

    left = round(placement.x * cw - size[0] / 2)
    top = round(placement.y * ch) - size[1]
    clamped_left = min(max(left, 0), cw - size[0])
    clamped_top = min(max(top, 0), ch - size[1])
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    layer.paste(product, (clamped_left, clamped_top))
    box = (clamped_left, clamped_top, clamped_left + size[0], clamped_top + size[1])
    return PlacedProduct(layer, box, scale, (clamped_left, clamped_top) != (left, top))


def contact_shadow(
    background: Image.Image, box: tuple[int, int, int, int], opacity: float = 0.45
) -> Image.Image:
    """Soft elliptical shadow where the product meets the surface (only background pixels change)."""
    left, _, right, bottom = box
    width = right - left
    height = max(6, round(width * 0.08))
    shadow = Image.new("L", background.size, 0)
    cx = (left + right) / 2
    ImageDraw.Draw(shadow).ellipse(
        (cx - width * 0.45, bottom - height / 2, cx + width * 0.45, bottom + height / 2), fill=255
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(3.0, height * 0.6)))
    shadow = shadow.point(lambda v: round(v * opacity))
    black = Image.new("RGB", background.size, (0, 0, 0))
    return Image.composite(black, background.convert("RGB"), shadow)


def composite(background: Image.Image, placed: PlacedProduct) -> Image.Image:
    base = background.convert("RGBA")
    if base.size != placed.layer.size:
        raise ValueError("Background and placement sizes differ.")
    return Image.alpha_composite(base, placed.layer).convert("RGB")


def _grow(mask: Image.Image, steps: int) -> Image.Image:
    for _ in range(steps):
        mask = mask.filter(ImageFilter.MaxFilter(3))
    return mask


def _shrink(mask: Image.Image, steps: int) -> Image.Image:
    for _ in range(steps):
        mask = mask.filter(ImageFilter.MinFilter(3))
    return mask


def opaque_mask(placed: PlacedProduct) -> Image.Image:
    return placed.layer.getchannel("A").point(lambda v: 255 if v == 255 else 0)


def protected_mask(placed: PlacedProduct, ring_px: int = 0) -> Image.Image:
    """Fully opaque product pixels, shrunk by `ring_px` when an edge ring is harmonised."""
    return _shrink(opaque_mask(placed), ring_px)


def edge_ring(placed: PlacedProduct, ring_px: int) -> Image.Image:
    """White band around the silhouette: `ring_px` outside the product plus `ring_px` inside its edge."""
    alpha = placed.layer.getchannel("A")
    outer = _grow(alpha.point(lambda v: 255 if v >= ALPHA_FLOOR else 0), ring_px)
    return ImageChops.subtract(outer, protected_mask(placed, ring_px))


def protect(result: Image.Image, reference: Image.Image, protected: Image.Image) -> Image.Image:
    """Copy `reference` pixels back wherever `protected` is white (the guarantee, not a best effort)."""
    return Image.composite(reference.convert("RGB"), result.convert("RGB"), protected)


def preservation_report(final: Image.Image, placed: PlacedProduct, protected: Image.Image) -> dict[str, Any]:
    """Compare protected product pixels in `final` with the placed original pixels."""
    reference = placed.layer.convert("RGB")
    diff = ImageChops.difference(final.convert("RGB"), reference)
    r, g, b = diff.split()
    channel_max = ImageChops.lighter(ImageChops.lighter(r, g), b)
    masked = ImageChops.multiply(channel_max, protected.point(lambda v: 1 if v == 255 else 0))
    protected_px = protected.histogram()[255]
    mismatched = sum(masked.point(lambda v: 255 if v > 0 else 0).histogram()[255:])
    max_diff = masked.getextrema()[1]
    opaque_px = opaque_mask(placed).histogram()[255]
    return {
        "protected_pixels": protected_px,
        "opaque_product_pixels": opaque_px,
        "mismatched_pixels": mismatched,
        "max_channel_diff": max_diff,
        "exact": protected_px > 0 and mismatched == 0,
        "scale": round(placed.scale, 4),
        "resampled": placed.scale != 1.0,
        "upscaled": placed.scale > 1.0,
        "clamped_to_frame": placed.clamped,
        "box": list(placed.box),
    }
