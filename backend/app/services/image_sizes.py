"""Aspect presets (multiples of 16, ~1 MP) shared with the frontend's lib/imageSizes.ts."""

from __future__ import annotations

from typing import Literal

AspectRatio = Literal["1:1", "4:5", "9:16", "16:9"]

ASPECT_SIZES: dict[AspectRatio, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "4:5": (896, 1120),
    "9:16": (768, 1360),
    "16:9": (1360, 768),
}
