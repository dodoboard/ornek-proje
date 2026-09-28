from __future__ import annotations

import random

import pytest
from PIL import Image, ImageChops, ImageDraw

from app.providers.segmentation.color_key import color_key_mask
from app.services.compositing import (
    Placement,
    composite,
    contact_shadow,
    edge_ring,
    make_cutout,
    place,
    preservation_report,
    protect,
    protected_mask,
)


def product_photo() -> tuple[Image.Image, tuple[int, int, int, int]]:
    """White studio background with a 'bottle' that has a white label and noisy logo inside."""
    img = Image.new("RGB", (400, 300), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    box = (150, 50, 250, 270)
    draw.rectangle(box, fill=(20, 60, 140))
    draw.rectangle((165, 120, 235, 200), fill=(250, 250, 250))  # white label (same as background!)
    rng = random.Random(3)
    for x in range(175, 225):
        for y in range(135, 185):
            img.putpixel((x, y), (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    return img, box


def test_color_key_keeps_interior_white_label() -> None:
    img, (x0, y0, x1, y1) = product_photo()
    mask = color_key_mask(img)
    assert mask.getpixel((5, 5)) == 0
    assert mask.getpixel((170, 125)) == 255  # white label inside the product stays foreground
    assert mask.getpixel((x0 + 2, y0 + 2)) == 255
    assert mask.crop((x0, y0, x1 + 1, y1 + 1)).getextrema() == (255, 255)


def test_cutout_keeps_original_rgb_and_crops() -> None:
    img, (x0, y0, x1, y1) = product_photo()
    cutout = make_cutout(img, color_key_mask(img))
    assert cutout.mode == "RGBA"
    assert cutout.size == (x1 - x0 + 1, y1 - y0 + 1)
    assert cutout.convert("RGB").tobytes() == img.crop((x0, y0, x1 + 1, y1 + 1)).tobytes()
    with pytest.raises(ValueError, match="empty"):
        make_cutout(img, Image.new("L", img.size, 0))


def test_native_scale_composite_is_pixel_identical() -> None:
    img, (x0, y0, x1, y1) = product_photo()
    cutout = make_cutout(img, color_key_mask(img))
    background = Image.new("RGB", (512, 512), (200, 180, 120))
    placed = place(cutout, background.size, Placement(x=0.5, y=0.9, native_scale=True))
    assert placed.scale == 1.0
    shaded = contact_shadow(background, placed.box)
    final = composite(shaded, placed)
    left, top, right, bottom = placed.box
    assert final.crop(placed.box).tobytes() == img.crop((x0, y0, x1 + 1, y1 + 1)).tobytes()
    report = preservation_report(final, placed, protected_mask(placed))
    assert report["exact"] and not report["resampled"]
    assert report["protected_pixels"] == (right - left) * (bottom - top)
    assert shaded.getpixel((256, bottom)) != background.getpixel((256, bottom))  # shadow darkens the floor


def test_scaled_placement_is_clamped_and_reported() -> None:
    img, _ = product_photo()
    cutout = make_cutout(img, color_key_mask(img))
    placed = place(cutout, (512, 512), Placement(x=0.98, y=0.5, height_ratio=0.8))
    assert placed.clamped
    assert placed.box[2] == 512
    assert placed.box[3] - placed.box[1] == round(0.8 * 512)
    report = preservation_report(
        composite(Image.new("RGB", (512, 512)), placed), placed, protected_mask(placed)
    )
    assert report["exact"] and report["upscaled"]
    with pytest.raises(ValueError, match="does not fit"):
        place(cutout, (100, 100), Placement(native_scale=True))


def test_harmonised_ring_never_touches_protected_core() -> None:
    img, _ = product_photo()
    cutout = make_cutout(img, color_key_mask(img))
    placed = place(cutout, (512, 512), Placement(native_scale=True))
    base = composite(Image.new("RGB", (512, 512), (90, 90, 90)), placed)
    ring = edge_ring(placed, 4)
    core = protected_mask(placed, 4)
    assert _overlap(ring, core) == 0
    noise = Image.effect_noise((512, 512), 80).convert("RGB")  # stands in for an AI edge re-render
    harmonised = Image.composite(noise, base, ring)
    final = protect(harmonised, placed.layer, core)
    report = preservation_report(final, placed, core)
    assert report["exact"]
    assert report["protected_pixels"] < report["opaque_product_pixels"]
    # Without the guarantee step the check catches the change.
    assert not preservation_report(Image.composite(noise, base, ring.point(lambda v: 255)), placed, core)[
        "exact"
    ]


def _overlap(a: Image.Image, b: Image.Image) -> int:
    return ImageChops.multiply(a, b).histogram()[255]


def test_soft_matte_interior_is_snapped_to_opaque() -> None:
    img, (x0, y0, x1, y1) = product_photo()
    soft = color_key_mask(img).point(lambda v: 254 if v else 3)  # like BiRefNet output
    cutout = make_cutout(img, soft)
    assert cutout.size == (x1 - x0 + 1, y1 - y0 + 1)
    assert cutout.getchannel("A").getextrema() == (255, 255)
