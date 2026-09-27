"""CharacterPromptBuilder: profile + bible → prompts for each character workflow step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.character import Character
from app.models.character_bible import CharacterBible
from app.services.prompts.base import join_nonempty, load_templates, render

CharacterPurpose = Literal["candidates", "front", "three_quarter", "full_body", "scene"]
PURPOSES: tuple[CharacterPurpose, ...] = ("candidates", "front", "three_quarter", "full_body", "scene")


@dataclass(frozen=True)
class CharacterPromptBuilder:
    character: Character
    bible: CharacterBible | None = None

    def identity(self) -> str:
        c = self.character
        subject = c.presentation.strip() or "adult"
        parts = [
            f"a {c.adult_age}-year-old {subject}",
            c.face_description,
            f"{c.hair} hair" if c.hair and "hair" not in c.hair.lower() else c.hair,
            f"{c.eye_color} eyes" if c.eye_color and "eye" not in c.eye_color.lower() else c.eye_color,
            c.skin_appearance,
            c.body_description,
            *(self.bible.immutable_traits if self.bible else []),
        ]
        return join_nonempty(parts)

    def build(self, purpose: CharacterPurpose, scene: str | None = None) -> str:
        templates = load_templates("character")["purposes"]
        c = self.character
        style = join_nonempty([c.style, c.default_prompt], sep=". ")
        values = {
            "identity": self.identity(),
            "style": f"Style: {style}." if style else "",
            "clothing": c.clothing_preferences.strip() or "simple well-fitted everyday clothes",
            "scene": (scene or "").strip(),
            "house_style": (self.bible.prompt_template if self.bible else "").strip(),
        }
        return render(templates[purpose], values)
