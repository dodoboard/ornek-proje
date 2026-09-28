"""ProductPromptBuilder: scene text + placement → prompts that leave room for the real product."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.prompts.base import load_templates, render


def position_phrase(x: float, y: float) -> str:
    horizontal = "on the left" if x < 0.36 else "on the right" if x > 0.64 else "in the centre"
    vertical = "lower part" if y > 0.6 else "upper part" if y < 0.4 else "middle"
    return f"{horizontal}, in the {vertical} of the frame"


@dataclass(frozen=True)
class ProductPromptBuilder:
    scene: str
    x: float = 0.5
    y: float = 0.85

    def _values(self) -> dict[str, str]:
        templates = load_templates("product")
        return {
            "scene": self.scene.strip().rstrip("."),
            "position": position_phrase(self.x, self.y),
            "house_style": str(templates.get("house_style") or ""),
        }

    def background(self) -> str:
        return render(str(load_templates("product")["background"]), self._values())

    def harmonize(self) -> str:
        return render(str(load_templates("product")["harmonize"]), self._values())
