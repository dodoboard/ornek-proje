"""Small generic helpers shared by the entity services."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.base import Base


def get_or_404[M: Base](session: Session, model: type[M], entity_id: str, label: str) -> M:
    obj = session.get(model, entity_id)
    if obj is None:
        raise NotFoundError(f"{label} not found.")
    return obj


def paginate[M: Base](session: Session, stmt: Select[M], limit: int, offset: int) -> tuple[list[M], int]:
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = list(session.scalars(stmt.limit(limit).offset(offset)))
    return items, total


def apply_updates(obj: Base, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(obj, key, value)
