from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.generation import Generation
from app.schemas.asset import AssetRead
from app.schemas.generation import GenerationRead
from app.services.crud import get_or_404, paginate


def to_read(session: Session, generation: Generation) -> GenerationRead:
    """Attach output assets (skipping any the user has since deleted)."""
    assets = []
    if generation.output_asset_ids:
        found = {
            a.id: a for a in session.scalars(select(Asset).where(Asset.id.in_(generation.output_asset_ids)))
        }
        assets = [AssetRead.model_validate(found[i]) for i in generation.output_asset_ids if i in found]
    read = GenerationRead.model_validate(generation)
    read.assets = assets
    return read


def list_generations(
    session: Session,
    *,
    kind: str | None,
    project_id: str | None,
    character_id: str | None,
    product_id: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Generation], int]:
    stmt = select(Generation).order_by(Generation.created_at.desc(), Generation.id.desc())
    kinds = [k for k in (kind or "").split(",") if k]
    if kinds:
        stmt = stmt.where(Generation.kind.in_(kinds))
    if project_id:
        stmt = stmt.where(Generation.project_id == project_id)
    if character_id:
        stmt = stmt.where(Generation.character_id == character_id)
    if product_id:
        stmt = stmt.where(Generation.product_id == product_id)
    return paginate(session, stmt, limit, offset)


def get_generation(session: Session, generation_id: str) -> Generation:
    return get_or_404(session, Generation, generation_id, "Generation")
