"""Pure-PIL helpers for editing: mask handling, outpaint canvases and exact pixel restoration.

Mask convention (same as Flux2KleinInpaintPipeline): white = repaint, black = keep.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter

from app.core.errors import FileInvalidError

MASK_THRESHOLD = 128


def snap_to_multiple(image: Image.Image, multiple: int) -> Image.Image:
    """Center-crop so both sides are multiples of `multiple` (the pipeline would otherwise resize)."""
    width = image.width - image.width % multiple
    height = image.height - image.height % multiple
    if width <= 0 or height <= 0:
        raise FileInvalidError(f"Image is smaller than {multiple}px.")
    if (width, height) == image.size:
        return image
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height))


def binarize(mask: Image.Image) -> Image.Image:
    return mask.convert("L").point(lambda v: 255 if v >= MASK_THRESHOLD else 0)


def load_mask(path: Path, size: tuple[int, int]) -> Image.Image:
    """Load a user mask as a binary L image matching `size` (nearest resize keeps hard edges)."""
    try:
        with Image.open(path) as img:
            mask = img.convert("L")
    except OSError as exc:
        raise FileInvalidError("The mask image could not be read.") from exc
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.NEAREST)
    mask = binarize(mask)
    if mask.getbbox() is None:
        raise FileInvalidError("The mask is empty — paint the area to change in white.")
    return mask


def feather(mask: Image.Image, radius: int) -> Image.Image:
    """Soft edge that only grows *into* the masked (white) side, so black pixels stay black."""
    if radius <= 0:
        return mask
    eroded = mask.filter(ImageFilter.MinFilter(radius * 2 + 1))
    blurred = eroded.filter(ImageFilter.GaussianBlur(radius))
    # Keep every originally-black pixel exactly black.
    return Image.composite(blurred, Image.new("L", mask.size, 0), mask)


@dataclass(frozen=True)
class OutpaintCanvas:
    canvas: Image.Image
    mask: Image.Image
    box: tuple[int, int, int, int]  # where the original sits: left, top, right, bottom


def outpaint_canvas(
    source: Image.Image, left: int, top: int, right: int, bottom: int, overlap: int = 16
) -> OutpaintCanvas:
    """Extend the source with edge-stretched borders; the mask covers the new area plus an overlap band."""
    width = source.width + left + right
    height = source.height + top + bottom
    canvas = source.resize((width, height), Image.Resampling.BILINEAR)  # plausible colors under the new area
    canvas.paste(source, (left, top))

    mask = Image.new("L", (width, height), 255)
    keep = (
        left + (overlap if left else 0),
        top + (overlap if top else 0),
        left + source.width - (overlap if right else 0),
        top + source.height - (overlap if bottom else 0),
    )
    mask.paste(0, keep)
    return OutpaintCanvas(canvas=canvas, mask=mask, box=(left, top, left + source.width, top + source.height))


def restore_unmasked(result: Image.Image, original: Image.Image, mask: Image.Image) -> Image.Image:
    """Take generated pixels only where the mask is white; black areas get the original bytes back.

    The VAE round-trip slightly alters every pixel, so this composite is what guarantees that
    untouched regions (product labels, logos, faces) are preserved exactly.
    """
    if result.size != original.size:
        result = result.resize(original.size, Image.Resampling.LANCZOS)
    return Image.composite(result.convert("RGB"), original.convert("RGB"), mask.convert("L"))
