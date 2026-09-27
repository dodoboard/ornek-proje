"""Character Studio workflows: bible, reference selection, prompt building, view assignment."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnsupportedFormatError
from app.db.base import utcnow
from app.models.character import Character
from app.models.character_bible import CharacterBible
from app.models.enums import AssetKind, AssetRole, ConsentSubject
from app.models.links import CharacterAsset
from app.schemas.character_studio import (
    VIEW_ROLES,
    CharacterBibleRead,
    CharacterBibleUpdate,
    CharacterGenerateRequest,
    PromptPreview,
)
from app.schemas.generation import ImageGenerateRequest
from app.services.assets import get_asset
from app.services.characters import get_character
from app.services.consents import require_active_consent
from app.services.crud import apply_updates
from app.services.image_sizes import ASPECT_SIZES, AspectRatio
from app.services.prompts.character import CharacterPromptBuilder, CharacterPurpose

SEED_HISTORY_LIMIT = 200
DEFAULT_ASPECT: dict[CharacterPurpose, AspectRatio] = {
    "candidates": "4:5",
    "front": "4:5",
    "three_quarter": "4:5",
    "full_body": "9:16",
    "scene": "9:16",
}


def get_or_create_bible(session: Session, character: Character) -> CharacterBible:
    bible = session.get(CharacterBible, character.id)
    if bible is None:
        bible = CharacterBible(
            character_id=character.id,
            visual_descriptors={},
            immutable_traits=[],
            mutable_traits=[],
            prompt_template="",
            negative_prompts=[],
            generation_settings={},
            seed_history=[],
        )
        session.add(bible)
        session.flush()
    return bible


def _links(character: Character, role: AssetRole) -> list[CharacterAsset]:
    return [link for link in character.assets if link.role is role]


def views(character: Character) -> dict[str, str | None]:
    return {
        role.value: next((link.asset_id for link in _links(character, role)), None) for role in VIEW_ROLES
    }


def bible_read(session: Session, character: Character) -> CharacterBibleRead:
    bible = get_or_create_bible(session, character)
    base = {c.key: getattr(bible, c.key) for c in CharacterBible.__table__.columns}
    return CharacterBibleRead(
        **base,
        views=views(character),
        reference_asset_ids=[link.asset_id for link in _links(character, AssetRole.REFERENCE)],
        identity=CharacterPromptBuilder(character, bible).identity(),
    )


def update_bible(session: Session, character_id: str, patch: CharacterBibleUpdate) -> CharacterBibleRead:
    character = get_character(session, character_id)
    bible = get_or_create_bible(session, character)
    apply_updates(bible, patch.model_dump(exclude_unset=True))
    session.commit()
    return bible_read(session, character)


def references_for(character: Character, purpose: CharacterPurpose, limit: int) -> list[str]:
    """Which images condition the model: uploads for candidates, canonical (+views) afterwards."""
    if purpose == "candidates":
        ids = [link.asset_id for link in _links(character, AssetRole.REFERENCE)]
    else:
        current = views(character)
        if current["canonical"] is None:
            raise ConflictError("Choose a canonical portrait before generating views or scenes.")
        order = ["canonical"] if purpose in ("front", "three_quarter", "full_body") else list(current)
        ids = [asset_id for role in order if (asset_id := current[role]) is not None]
    return list(dict.fromkeys(ids))[: max(0, limit)]


def preview(
    session: Session, character: Character, body: CharacterGenerateRequest, max_references: int
) -> PromptPreview:
    bible = get_or_create_bible(session, character)
    aspect = body.aspect_ratio or DEFAULT_ASPECT[body.purpose]
    width, height = ASPECT_SIZES[aspect]
    return PromptPreview(
        purpose=body.purpose,
        prompt=CharacterPromptBuilder(character, bible).build(body.purpose, body.scene),
        reference_asset_ids=references_for(character, body.purpose, max_references),
        width=width,
        height=height,
    )


def build_image_request(
    session: Session, character: Character, body: CharacterGenerateRequest, max_references: int
) -> ImageGenerateRequest:
    if character.is_real_person:
        require_active_consent(session, character.consent_id, ConsentSubject.FACE)
    plan = preview(session, character, body, max_references)
    return ImageGenerateRequest(
        prompt=plan.prompt,
        width=plan.width,
        height=plan.height,
        steps=body.steps,
        seed=body.seed,
        num_images=body.num_images,
        model_key=body.model_key,
        reference_asset_ids=plan.reference_asset_ids,
        project_id=body.project_id,
        character_id=character.id,
        purpose=body.purpose,
    )


def set_view(session: Session, character_id: str, role: AssetRole, asset_id: str) -> Character:
    """Assign an image to a view slot, replacing whatever held that slot before."""
    if role not in VIEW_ROLES:
        raise UnsupportedFormatError(f"'{role.value}' is not a character view.")
    character = get_character(session, character_id)
    if character.is_real_person:
        require_active_consent(session, character.consent_id, ConsentSubject.FACE)
    asset = get_asset(session, asset_id)
    if asset.kind is not AssetKind.IMAGE:
        raise UnsupportedFormatError("Character views must be images.")
    owner = (asset.metadata_json or {}).get("character_id")
    if owner not in (None, character.id):
        raise ConflictError("This image was generated for a different character.")
    for link in _links(character, role):
        character.assets.remove(link)
    session.flush()
    character.assets.append(
        CharacterAsset(character_id=character.id, asset_id=asset_id, role=role, position=0)
    )
    session.commit()
    return character


def record_seeds(
    session: Session,
    character_id: str,
    purpose: str,
    generation_id: str,
    model: str,
    outputs: list[tuple[str, int]],
) -> None:
    """Append (asset_id, seed) pairs to the bible's seed history (caller commits)."""
    character = session.get(Character, character_id)
    if character is None:
        return
    bible = get_or_create_bible(session, character)
    now = utcnow().isoformat()
    entries: list[dict[str, Any]] = [
        {"seed": seed, "purpose": purpose, "generation_id": generation_id, "asset_id": asset_id,
         "model": model, "created_at": now}
        for asset_id, seed in outputs
    ]  # fmt: skip
    bible.seed_history = [*bible.seed_history, *entries][-SEED_HISTORY_LIMIT:]
