from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from app.core.errors import FileInvalidError
from app.services.image_edit import feather, load_mask, outpaint_canvas, restore_unmasked, snap_to_multiple


def _noise(size: tuple[int, int], seed: int) -> Image.Image:
    import random

    rng = random.Random(seed)
    return Image.frombytes("RGB", size, bytes(rng.randrange(256) for _ in range(size[0] * size[1] * 3)))


def test_snap_to_multiple_center_crops() -> None:
    snapped = snap_to_multiple(Image.new("RGB", (1030, 770)), 16)
    assert snapped.size == (1024, 768)
    assert snap_to_multiple(Image.new("RGB", (64, 64)), 16).size == (64, 64)
    with pytest.raises(FileInvalidError):
        snap_to_multiple(Image.new("RGB", (8, 8)), 16)


def test_load_mask_binarizes_and_resizes(tmp_path: Path) -> None:
    src = Image.new("RGB", (50, 40), (0, 0, 0))
    ImageDraw.Draw(src).rectangle((10, 10, 20, 20), fill=(200, 200, 200))
    ImageDraw.Draw(src).rectangle((30, 10, 40, 20), fill=(90, 90, 90))  # below threshold → keep
    path = tmp_path / "m.png"
    src.save(path)
    mask = load_mask(path, (100, 80))
    assert mask.mode == "L" and mask.size == (100, 80)
    assert set(mask.getdata()) == {0, 255}
    assert mask.getpixel((30, 30)) == 255 and mask.getpixel((70, 30)) == 0


def test_empty_mask_rejected(tmp_path: Path) -> None:
    path = tmp_path / "m.png"
    Image.new("L", (32, 32), 0).save(path)
    with pytest.raises(FileInvalidError):
        load_mask(path, (32, 32))


def test_feather_never_touches_black_pixels() -> None:
    mask = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(mask).rectangle((16, 16, 47, 47), fill=255)
    soft = feather(mask, 4)
    for x, y in [(15, 30), (0, 0), (48, 48)]:
        assert soft.getpixel((x, y)) == 0
    assert soft.getpixel((32, 32)) == 255
    assert 0 < soft.getpixel((17, 32)) < 255


def test_restore_unmasked_is_byte_exact_outside_mask() -> None:
    original = _noise((64, 48), 1)
    generated = _noise((64, 48), 2)
    mask = Image.new("L", (64, 48), 0)
    ImageDraw.Draw(mask).rectangle((20, 10, 40, 30), fill=255)
    out = restore_unmasked(generated, original, feather(mask, 3))
    diff = ImageChops.difference(out, original)
    inverse = mask.point(lambda v: 255 - v)
    assert ImageChops.multiply(diff.convert("L"), inverse).getbbox() is None
    got, want = out.getpixel((30, 20)), generated.getpixel((30, 20))
    assert all(abs(a - b) <= 2 for a, b in zip(got, want, strict=True))  # soft edge tails, ~fully generated


def test_outpaint_canvas_geometry() -> None:
    source = _noise((64, 48), 3)
    result = outpaint_canvas(source, left=32, top=0, right=16, bottom=16, overlap=8)
    assert result.canvas.size == (112, 64)
    assert result.box == (32, 0, 96, 48)
    assert result.canvas.crop(result.box).tobytes() == source.tobytes()
    m = result.mask
    assert m.getpixel((0, 10)) == 255  # new left area
    assert m.getpixel((35, 10)) == 255  # overlap band on the left edge
    assert m.getpixel((60, 5)) == 0  # original interior, top edge not extended
    assert m.getpixel((60, 60)) == 255  # new bottom area
