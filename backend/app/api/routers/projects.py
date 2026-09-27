from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import PaginationDep, SessionDep
from app.models.enums import ProjectType
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services import projects as service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectRead])
def list_projects(
    session: SessionDep, page: PaginationDep, type: ProjectType | None = None
) -> Page[ProjectRead]:
    items, total = service.list_projects(session, type, page.limit, page.offset)
    return Page(items=[ProjectRead.model_validate(i) for i in items], total=total, **page.__dict__)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: SessionDep) -> ProjectRead:
    return ProjectRead.model_validate(service.create_project(session, payload))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: SessionDep) -> ProjectRead:
    return ProjectRead.model_validate(service.get_project(session, project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, payload: ProjectUpdate, session: SessionDep) -> ProjectRead:
    return ProjectRead.model_validate(service.update_project(session, project_id, payload))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, session: SessionDep) -> None:
    service.delete_project(session, project_id)
