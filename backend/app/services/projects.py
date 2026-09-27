from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import IdPrefix, new_id
from app.models.enums import ProjectType
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.characters import get_character
from app.services.crud import apply_updates, get_or_404, paginate
from app.services.products import get_product
from app.services.properties import get_property


def _check_references(session: Session, values: dict[str, Any]) -> None:
    if values.get("character_id"):
        get_character(session, values["character_id"])
    if values.get("product_id"):
        get_product(session, values["product_id"])
    if values.get("property_id"):
        get_property(session, values["property_id"])


def create_project(session: Session, payload: ProjectCreate) -> Project:
    values = payload.model_dump(mode="json")
    _check_references(session, values)
    project = Project(id=new_id(IdPrefix.PROJECT), **values)
    session.add(project)
    session.commit()
    return project


def list_projects(
    session: Session, project_type: ProjectType | None, limit: int, offset: int
) -> tuple[list[Project], int]:
    stmt = select(Project).order_by(Project.updated_at.desc())
    if project_type is not None:
        stmt = stmt.where(Project.type == project_type)
    return paginate(session, stmt, limit, offset)


def get_project(session: Session, project_id: str) -> Project:
    return get_or_404(session, Project, project_id, "Project")


def update_project(session: Session, project_id: str, payload: ProjectUpdate) -> Project:
    project = get_project(session, project_id)
    values = payload.model_dump(mode="json", exclude_unset=True)
    _check_references(session, values)
    apply_updates(project, values)
    session.commit()
    return project


def delete_project(session: Session, project_id: str) -> None:
    session.delete(get_project(session, project_id))
    session.commit()
