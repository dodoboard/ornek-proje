"""Persist scripts as versioned storyboards and let the user edit, add, delete and reorder shots."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.ids import IdPrefix, new_id
from app.models.character import Character
from app.models.project import Project
from app.models.script import Script, Shot, Storyboard
from app.schemas.script import DEFAULT_DISCLOSURE, DEFAULT_METHOD, ShotCreate, ShotDraft, ShotUpdate
from app.services.crud import get_or_404
from app.services.script_engine import ScriptResult


def presenter_text(session: Session, project: Project) -> str:
    if not project.character_id or (c := session.get(Character, project.character_id)) is None:
        return ""
    parts = [
        f"{c.name}, {c.adult_age}-year-old {c.presentation or 'adult'}",
        c.personality,
        c.speaking_style,
        c.brand_tone,
    ]
    return "; ".join(p.strip() for p in parts if p and p.strip())


def _shot_from_draft(storyboard_id: str, position: int, draft: ShotDraft) -> Shot:
    method = DEFAULT_METHOD[draft.type]
    return Shot(
        id=new_id(IdPrefix.SHOT),
        storyboard_id=storyboard_id,
        position=position,
        type=draft.type,
        duration_s=draft.duration_s,
        description=draft.description,
        dialogue=draft.dialogue,
        on_screen_text=draft.on_screen_text,
        visual_prompt=draft.visual_prompt,
        camera=draft.camera,
        camera_motion=draft.camera_motion,
        generation_method=method,
        disclosure_label=DEFAULT_DISCLOSURE[method],
    )


def save_script(
    session: Session, project: Project, result: ScriptResult, brief: str, language: str
) -> tuple[Script, Storyboard]:
    script = Script(
        id=new_id(IdPrefix.SCRIPT),
        project_id=project.id,
        source=result.source,
        llm_model=result.llm_model,
        language=language,
        title=result.draft.title,
        hook=result.draft.hook,
        cta=result.draft.cta,
        brief=brief,
        content=result.raw.model_dump(mode="json"),
        attempts=result.attempts,
        fact_report={"placeholders": result.placeholders, "violations": []},
    )
    session.add(script)
    version = (
        session.scalar(select(func.max(Storyboard.version)).where(Storyboard.project_id == project.id)) or 0
    ) + 1
    storyboard = Storyboard(
        id=new_id(IdPrefix.STORYBOARD),
        project_id=project.id,
        script_id=script.id,
        version=version,
        aspect_ratio=str(project.settings.get("aspect_ratio", "9:16")),
    )
    session.add(storyboard)
    session.flush()
    for i, draft in enumerate(result.draft.shots):
        session.add(_shot_from_draft(storyboard.id, i, draft))
    session.commit()
    session.refresh(storyboard)
    return script, storyboard


def latest_storyboard(session: Session, project_id: str) -> Storyboard:
    get_or_404(session, Project, project_id, "Project")
    stmt = (
        select(Storyboard)
        .where(Storyboard.project_id == project_id)
        .order_by(Storyboard.version.desc())
        .limit(1)
    )
    storyboard = session.scalar(stmt)
    if storyboard is None:
        raise NotFoundError("This project has no storyboard yet. Generate a script first.")
    return storyboard


def list_scripts(session: Session, project_id: str) -> list[Script]:
    get_or_404(session, Project, project_id, "Project")
    stmt = select(Script).where(Script.project_id == project_id).order_by(Script.created_at.desc())
    return list(session.scalars(stmt))


def _renumber(storyboard: Storyboard) -> None:
    for i, shot in enumerate(sorted(storyboard.shots, key=lambda s: s.position)):
        shot.position = i


def update_shot(session: Session, shot_id: str, patch: ShotUpdate) -> Shot:
    shot = get_or_404(session, Shot, shot_id, "Shot")
    values = patch.model_dump(exclude_unset=True, exclude_none=True)
    if "generation_method" in values and "disclosure_label" not in values:
        values["disclosure_label"] = DEFAULT_DISCLOSURE[values["generation_method"]]
    for key, value in values.items():
        setattr(shot, key, value)
    if values:
        shot.edited = True
    session.commit()
    return shot


def add_shot(session: Session, storyboard_id: str, body: ShotCreate) -> Storyboard:
    storyboard = get_or_404(session, Storyboard, storyboard_id, "Storyboard")
    if len(storyboard.shots) >= 100:
        raise ConflictError("A storyboard can have at most 100 shots.")
    draft = ShotDraft(type=body.type, duration_s=min(15.0, max(1.0, body.duration_s or 3)))
    shot = _shot_from_draft(storyboard.id, len(storyboard.shots), draft)
    for key, value in body.model_dump(exclude_none=True, exclude={"position", "type"}).items():
        setattr(shot, key, value)
    if body.generation_method and not body.disclosure_label:
        shot.disclosure_label = DEFAULT_DISCLOSURE[body.generation_method]
    shot.edited = True
    position = len(storyboard.shots) if body.position is None else min(body.position, len(storyboard.shots))
    for existing in storyboard.shots:
        if existing.position >= position:
            existing.position += 1
    shot.position = position
    storyboard.shots.append(shot)
    _renumber(storyboard)
    session.commit()
    session.refresh(storyboard)
    return storyboard


def delete_shot(session: Session, shot_id: str) -> None:
    shot = get_or_404(session, Shot, shot_id, "Shot")
    storyboard = get_or_404(session, Storyboard, shot.storyboard_id, "Storyboard")
    if len(storyboard.shots) <= 1:
        raise ConflictError("A storyboard needs at least one shot.")
    storyboard.shots.remove(shot)
    _renumber(storyboard)
    session.commit()


def reorder(session: Session, storyboard_id: str, shot_ids: list[str]) -> Storyboard:
    storyboard = get_or_404(session, Storyboard, storyboard_id, "Storyboard")
    current = {s.id: s for s in storyboard.shots}
    if len(shot_ids) != len(current) or set(shot_ids) != set(current):
        raise ConflictError("The new order must list every shot of this storyboard exactly once.")
    for i, shot_id in enumerate(shot_ids):
        current[shot_id].position = i
    session.commit()
    session.refresh(storyboard)
    return storyboard
