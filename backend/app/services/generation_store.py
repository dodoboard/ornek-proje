"""Persist image outputs + provenance in one transaction (shared by generate and edit jobs)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PIL.Image import Image
from sqlalchemy.orm import Session

from app.core.ids import IdPrefix, new_id
from app.db.base import utcnow
from app.models.generation import Generation
from app.services.character_studio import record_seeds
from app.services.generated_media import delete_media_files, store_generated_image
from app.services.storage import StorageService


@dataclass
class ImageGenerationRecord:
    kind: str
    job_id: str
    provider: str
    model_key: str
    model_source: str | None
    placeholder: bool
    seeds: list[int]
    params: dict[str, Any]
    input_asset_ids: list[str]
    duration_ms: int
    device: dict[str, Any] | None
    watermark: bool
    project_id: str | None = None
    character_id: str | None = None
    product_id: str | None = None
    purpose: str | None = None
    #: False when no AI model produced any pixel (e.g. a product composited onto a user photo).
    ai_generated: bool = True
    extra_disclosure: dict[str, Any] = field(default_factory=dict)


def save_image_generation(
    session_factory: Callable[[], Session],
    storage: StorageService,
    images: list[Image],
    record: ImageGenerationRecord,
) -> tuple[str, list[str]]:
    """Store every image with disclosure metadata, the Generation row and seed history.

    Files written before a failure are removed so the DB and disk never disagree.
    """
    generation_id = new_id(IdPrefix.GENERATION)
    created_at = utcnow().isoformat()
    stored = []
    with session_factory() as session:
        try:
            for image, seed in zip(images, record.seeds, strict=True):
                disclosure = {
                    "generated_with_ai": record.ai_generated and not record.placeholder,
                    "dev_placeholder": record.placeholder,
                    "model": record.model_key,
                    "provider": record.provider,
                    "seed": seed,
                    "created_at": created_at,
                    "generation_id": generation_id,
                    "project_id": record.project_id,
                    "character_id": record.character_id,
                    **({"product_id": record.product_id} if record.product_id else {}),
                    "source_asset_ids": record.input_asset_ids,
                    **record.extra_disclosure,
                }
                stored.append(
                    store_generated_image(
                        session,
                        storage,
                        image,
                        disclosure,
                        watermark=record.watermark,
                        ai_generated=record.ai_generated,
                    )
                )
            session.add(
                Generation(
                    id=generation_id,
                    kind=record.kind,
                    job_id=record.job_id,
                    project_id=record.project_id,
                    character_id=record.character_id,
                    product_id=record.product_id,
                    provider=record.provider,
                    model_key=record.model_key,
                    model_source=record.model_source,
                    params={"watermark": record.watermark, "purpose": record.purpose, **record.params},
                    seeds=record.seeds,
                    input_asset_ids=record.input_asset_ids,
                    output_asset_ids=[a.id for a in stored],
                    duration_ms=record.duration_ms,
                    device=record.device,
                )
            )
            if record.character_id and record.purpose:
                record_seeds(
                    session,
                    record.character_id,
                    record.purpose,
                    generation_id,
                    record.model_key,
                    [(a.id, s) for a, s in zip(stored, record.seeds, strict=True)],
                )
            session.commit()
        except BaseException:
            session.rollback()
            delete_media_files(storage, stored)
            raise
    return generation_id, [a.id for a in stored]
