"""Script generation (queued job) and storyboard editing."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import SessionDep, SettingsDep
from app.models.project import Project
from app.models.script import Shot, Storyboard
from app.providers.base import ProviderKind
from app.schemas.job import JobRead
from app.schemas.script import (
    ScriptGenerateRequest,
    ScriptRead,
    ShotCreate,
    ShotOrder,
    ShotRead,
    ShotUpdate,
    StoryboardRead,
)
from app.services import storyboards as service
from app.services.crud import get_or_404
from app.services.model_selection import require_available
from app.services.preferences import build_registry, load_preferences
from app.workers.handlers.script_generate import JOB_TYPE as SCRIPT_JOB
from app.workers.queue import JobQueue

router = APIRouter(tags=["storyboards"])


def _read(storyboard: Storyboard) -> StoryboardRead:
    return StoryboardRead.model_validate(storyboard)


@router.post("/projects/{project_id}/script", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def generate_script(
    project_id: str, body: ScriptGenerateRequest, request: Request, session: SessionDep, settings: SettingsDep
) -> JobRead:
    """Write a script with the local LLM (facts only via placeholders); falls back to a template."""
    get_or_404(session, Project, project_id, "Project")
    payload = body.model_dump(mode="json")
    if not body.template_only:
        registry = build_registry(settings, load_preferences(session, settings))
        payload["llm_model_key"] = require_available(registry, ProviderKind.LLM, body.llm_model_key).key
    job = JobQueue(request.app.state.session_factory).enqueue(
        SCRIPT_JOB, {**payload, "project_id": project_id}, project_id=project_id
    )
    return JobRead.model_validate(job)


@router.get("/projects/{project_id}/scripts", response_model=list[ScriptRead])
def list_scripts(project_id: str, session: SessionDep) -> list[ScriptRead]:
    return [ScriptRead.model_validate(s) for s in service.list_scripts(session, project_id)]


@router.get("/projects/{project_id}/storyboard", response_model=StoryboardRead)
def latest_storyboard(project_id: str, session: SessionDep) -> StoryboardRead:
    return _read(service.latest_storyboard(session, project_id))


@router.get("/storyboards/{storyboard_id}", response_model=StoryboardRead)
def get_storyboard(storyboard_id: str, session: SessionDep) -> StoryboardRead:
    return _read(get_or_404(session, Storyboard, storyboard_id, "Storyboard"))


@router.post(
    "/storyboards/{storyboard_id}/shots", response_model=StoryboardRead, status_code=status.HTTP_201_CREATED
)
def add_shot(storyboard_id: str, body: ShotCreate, session: SessionDep) -> StoryboardRead:
    return _read(service.add_shot(session, storyboard_id, body))


@router.put("/storyboards/{storyboard_id}/order", response_model=StoryboardRead)
def reorder(storyboard_id: str, body: ShotOrder, session: SessionDep) -> StoryboardRead:
    return _read(service.reorder(session, storyboard_id, body.shot_ids))


@router.patch("/shots/{shot_id}", response_model=ShotRead)
def update_shot(shot_id: str, body: ShotUpdate, session: SessionDep) -> ShotRead:
    return ShotRead.model_validate(service.update_shot(session, shot_id, body))


@router.delete("/shots/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shot(shot_id: str, session: SessionDep) -> None:
    get_or_404(session, Shot, shot_id, "Shot")
    service.delete_shot(session, shot_id)
