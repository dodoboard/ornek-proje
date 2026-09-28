"""`script.generate`: project facts → ScriptEngine (local LLM or template) → new storyboard version."""

from __future__ import annotations

import logging
from contextlib import ExitStack
from typing import Any

from app.core.errors import AppError
from app.models.enums import JobStatus
from app.models.project import Project
from app.providers.base import LLMProvider, ProviderKind
from app.schemas.script import ScriptGenerateRequest
from app.services.crud import get_or_404
from app.services.facts import collect_facts
from app.services.script_engine import ScriptContext, ScriptEngine
from app.services.storyboards import presenter_text, save_script
from app.workers.context import JobContext

logger = logging.getLogger(__name__)

JOB_TYPE = "script.generate"


def run_script_generate(ctx: JobContext) -> dict[str, Any]:
    project_id = str(ctx.payload.get("project_id"))
    request = ScriptGenerateRequest.model_validate(
        {k: v for k, v in ctx.payload.items() if k != "project_id"}
    )

    with ctx.session() as session:
        project = get_or_404(session, Project, project_id, "Project")
        settings = dict(project.settings or {})
        facts = collect_facts(session, project, request.brief)
        script_ctx = ScriptContext(
            project_type=project.type,
            language=str(settings.get("language", "tr")),
            platform=str(settings.get("platform", "generic")),
            duration_s=int(settings.get("duration_s", 30)),
            tone=str(settings.get("tone", "professional")),
            aspect_ratio=str(settings.get("aspect_ratio", "9:16")),
            presenter=presenter_text(session, project),
            brief=request.brief,
            facts=facts,
        )

    pre_attempts: list[dict[str, Any]] = []
    with ExitStack() as stack:
        llm: LLMProvider | None = None
        if not request.template_only:
            ctx.report(5, status=JobStatus.LOADING_MODEL, stage="Connecting to the local LLM")
            try:
                llm = stack.enter_context(
                    ctx.models.use(ProviderKind.LLM, LLMProvider, request.llm_model_key)
                )
            except AppError as exc:  # server down / model not pulled: fall back to the template
                pre_attempts.append({"attempt": 0, "ok": False, "errors": [exc.message]})
        ctx.report(15, status=JobStatus.GENERATING_SCRIPT, stage="Writing the script")
        result = ScriptEngine(script_ctx, llm, check_cancel=lambda: ctx.report(None)).run()
    result.attempts = pre_attempts + result.attempts

    ctx.report(85, status=JobStatus.GENERATING_STORYBOARD, stage="Building the storyboard")
    with ctx.session() as session:
        project = get_or_404(session, Project, project_id, "Project")
        script, storyboard = save_script(session, project, result, request.brief, script_ctx.language)
        response = {
            "script_id": script.id,
            "storyboard_id": storyboard.id,
            "version": storyboard.version,
            "source": result.source,
            "shots": len(storyboard.shots),
        }
    logger.info("script_generated", extra={"project_id": project_id, "source": result.source})
    return response
