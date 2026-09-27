"""DEV/TEST ONLY placeholder image provider. Draws a labelled gradient — it is not an AI model."""

from __future__ import annotations

import hashlib
import textwrap

from PIL import Image, ImageDraw

from app.providers.base import (
    Availability,
    GenerationContext,
    ImageCapabilities,
    ImageGenerationProvider,
    ImageRequest,
    Maturity,
    ProviderStatus,
)
from app.providers.device import DeviceInfo

LABEL = "DEV PLACEHOLDER - NOT AI OUTPUT"


class FakeImageProvider(ImageGenerationProvider):
    maturity = Maturity.DEV_ONLY
    heavy = False

    def availability(self) -> Availability:
        return Availability(ProviderStatus.AVAILABLE, "Development placeholder; produces labelled gradients.")

    def capabilities(self) -> ImageCapabilities:
        return ImageCapabilities(
            text_to_image=True, image_edit=False, max_reference_images=0, inpainting=False,
            negative_prompt=False, guidance=False, min_size=64, max_size=2048, size_multiple=16,
            max_images_per_request=4, default_steps=4,
        )  # fmt: skip

    def load(self, device: DeviceInfo) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate(self, request: ImageRequest, ctx: GenerationContext) -> list[Image.Image]:
        images = []
        for index in range(request.num_images):
            seed = request.seed + index
            for step in range(request.steps):
                ctx.progress((index * request.steps + step + 1) / (request.num_images * request.steps))
            images.append(render_placeholder(request.width, request.height, seed, request.prompt))
        return images


def render_placeholder(width: int, height: int, seed: int, text: str) -> Image.Image:
    digest = hashlib.sha256(f"{seed}:{text}".encode()).digest()
    start, end = digest[:3], digest[3:6]
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(start[c] + (end[c] - start[c]) * t) for c in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    lines = [LABEL, f"seed {seed}", *textwrap.wrap(text, 48)[:4]]
    draw.multiline_text((16, 16), "\n".join(lines), fill=(255, 255, 255), spacing=6)
    return image
