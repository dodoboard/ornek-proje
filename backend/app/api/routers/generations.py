from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import PaginationDep, SessionDep
from app.schemas.common import Page
from app.schemas.generation import GenerationRead
from app.services import generations as service

router = APIRouter(prefix="/generations", tags=["generations"])


@router.get("", response_model=Page[GenerationRead])
def list_generations(
    session: SessionDep,
    page: PaginationDep,
    kind: Annotated[
        str | None, Query(max_length=60, description="Comma-separated kinds, e.g. image,image_edit")
    ] = None,
    project_id: Annotated[str | None, Query(max_length=40)] = None,
    character_id: Annotated[str | None, Query(max_length=40)] = None,
    product_id: Annotated[str | None, Query(max_length=40)] = None,
) -> Page[GenerationRead]:
    items, total = service.list_generations(
        session,
        kind=kind,
        project_id=project_id,
        character_id=character_id,
        product_id=product_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=[service.to_read(session, g) for g in items], total=total, **page.__dict__)


@router.get("/{generation_id}", response_model=GenerationRead)
def get_generation(generation_id: str, session: SessionDep) -> GenerationRead:
    return service.to_read(session, service.get_generation(session, generation_id))
