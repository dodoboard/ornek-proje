from __future__ import annotations

import pytest

from app.models.character import Character
from app.models.character_bible import CharacterBible
from app.services.prompts.base import render
from app.services.prompts.character import PURPOSES, CharacterPromptBuilder


def _character(**overrides: object) -> Character:
    fields = dict(
        name="A", adult_age=31, presentation="man", face_description="square jaw", hair="short black",
        eye_color="brown", skin_appearance="warm olive skin", body_description="", style="streetwear",
        default_prompt="", clothing_preferences="",
    )  # fmt: skip
    fields.update(overrides)
    return Character(**fields)


def test_identity_is_complete_and_ordered() -> None:
    bible = CharacterBible(immutable_traits=["scar on right eyebrow"], prompt_template="")
    identity = CharacterPromptBuilder(_character(), bible).identity()
    expected = (
        "a 31-year-old man, square jaw, short black hair, brown eyes, warm olive skin, scar on right eyebrow"
    )
    assert identity == expected


def test_hair_and_eye_suffixes_not_duplicated() -> None:
    identity = CharacterPromptBuilder(_character(hair="bald, no hair", eye_color="green eyes")).identity()
    assert "no hair hair" not in identity and "eyes eyes" not in identity


def test_empty_presentation_defaults_to_adult() -> None:
    assert CharacterPromptBuilder(_character(presentation="")).identity().startswith("a 31-year-old adult")


@pytest.mark.parametrize("purpose", PURPOSES)
def test_every_purpose_renders_cleanly(purpose: str) -> None:
    prompt = CharacterPromptBuilder(_character()).build(purpose, scene="walking in Istanbul")  # type: ignore[arg-type]
    assert "{" not in prompt and "  " not in prompt and ". ." not in prompt
    assert "31-year-old man" in prompt


def test_user_braces_are_not_template_injection() -> None:
    prompt = CharacterPromptBuilder(_character(style="{identity}{scene}")).build("candidates")
    assert "{identity}{scene}" in prompt


def test_render_cleans_empty_slots() -> None:
    assert render("A {x}, {y}. {z} end", {"x": "cat"}) == "A cat. end"
