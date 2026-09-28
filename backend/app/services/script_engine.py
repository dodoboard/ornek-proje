"""ScriptEngine: local LLM → JSON schema → validation → FactGuard → (1 repair) → template fallback.

It never raises for bad model output: the worst case is the deterministic template script, and every
attempt with its rejection reasons is recorded so the user can see why.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.core.errors import AppError, GenerationFailedError
from app.models.enums import ProjectType
from app.providers.base import LLMProvider
from app.schemas.script import ScriptDraft, ShotDraft, llm_schema
from app.services import fact_guard
from app.services.facts import FactSheet
from app.services.prompts.base import load_templates

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"tr": "Turkish", "en": "English"}
_COMMON = ("hook", "talking_head", "broll", "text_card", "cta")
ALLOWED_TYPES: dict[ProjectType, tuple[str, ...]] = {
    ProjectType.PRODUCT_AD: (*_COMMON, "product_closeup", "product_in_use"),
    ProjectType.SOCIAL: (*_COMMON, "product_in_use"),
    ProjectType.REAL_ESTATE: (*_COMMON, "property_exterior", "property_interior"),
    ProjectType.LAND: (*_COMMON, "land_overview", "property_exterior"),
}
ALL_TYPES = tuple(sorted({t for types in ALLOWED_TYPES.values() for t in types}))
MAX_ATTEMPTS = 2


class _Blank(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


def fill(template: str, values: dict[str, str]) -> str:
    return template.format_map(_Blank(values)).strip()


@dataclass(frozen=True)
class ScriptContext:
    project_type: ProjectType
    language: str
    platform: str
    duration_s: int
    tone: str
    aspect_ratio: str
    presenter: str
    brief: str
    facts: FactSheet

    @property
    def allowed_types(self) -> tuple[str, ...]:
        return ALLOWED_TYPES.get(self.project_type, ALL_TYPES)

    @property
    def is_property(self) -> bool:
        return self.project_type in (ProjectType.REAL_ESTATE, ProjectType.LAND)


@dataclass
class ScriptResult:
    draft: ScriptDraft  # facts rendered
    raw: ScriptDraft  # with {{placeholders}}
    source: str  # "llm" | "template"
    llm_model: str | None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)


def normalize_durations(draft: ScriptDraft, target: float) -> ScriptDraft:
    """Scale shot durations to the target total (0.5 s steps, ≥1 s per shot); rounding drift goes to the
    longest shot so the total is exact whenever the minimums allow it."""
    total = sum(s.duration_s for s in draft.shots)
    factor = target / total if total else 1.0
    seconds = [max(1.0, round(s.duration_s * factor * 2) / 2) for s in draft.shots]
    longest = max(range(len(seconds)), key=seconds.__getitem__)
    seconds[longest] = max(1.0, seconds[longest] + target - sum(seconds))
    shots = [s.model_copy(update={"duration_s": d}) for s, d in zip(draft.shots, seconds, strict=True)]
    return draft.model_copy(update={"shots": shots})


def structural_errors(draft: ScriptDraft, ctx: ScriptContext) -> list[str]:
    errors = [
        f"shots[{i}].type '{s.type}' is not allowed for a {ctx.project_type.value} project"
        for i, s in enumerate(draft.shots)
        if s.type not in ctx.allowed_types
    ]
    if not any(s.dialogue or s.on_screen_text for s in draft.shots):
        errors.append("the script has no dialogue or on-screen text")
    return errors


def render_draft(draft: ScriptDraft, facts: FactSheet) -> ScriptDraft:
    def r(text: str) -> str:
        return facts.render(text)[0]

    shots = [
        s.model_copy(
            update={
                "dialogue": r(s.dialogue),
                "on_screen_text": r(s.on_screen_text),
                "description": r(s.description),
            }
        )
        for s in draft.shots
    ]
    return draft.model_copy(
        update={"title": r(draft.title), "hook": r(draft.hook), "cta": r(draft.cta), "shots": shots}
    )


def used_placeholders(draft: ScriptDraft, facts: FactSheet) -> list[str]:
    from app.services.facts import PLACEHOLDER_RE

    keys = {m.group(1) for _, text in fact_guard.all_fields(draft) for m in PLACEHOLDER_RE.finditer(text)}
    return sorted(k for k in keys if k in facts.values)


# --------------------------------------------------------------------------- template


def _shot(kind: str, seconds: float, **fields: str) -> ShotDraft:
    camera = "close_up" if kind in ("product_closeup", "talking_head") else "wide"
    return ShotDraft.model_validate({"type": kind, "duration_s": seconds, "camera": camera, **fields})


def template_script(ctx: ScriptContext) -> ScriptDraft:
    """Deterministic script built only from verified placeholders and fixed, claim-free sentences."""
    t: dict[str, str] = load_templates("script")["template"]["tr" if ctx.language.startswith("tr") else "en"]
    facts = ctx.facts.values

    def ph(key: str) -> str:
        return f"{{{{{key}}}}}" if key in facts else ""

    if ctx.is_property:
        land = ctx.project_type is ProjectType.LAND
        overview = "land_overview" if land else "property_exterior"
        area = ph("property.land_sqm") or ph("property.sqm")
        intro = t["talking_property"] if "property.location" in facts else t["hook_property"]
        footage = "real listing footage"
        shots = [
            _shot(overview, 3, on_screen_text=ph("property.title"), description="Establishing view",
                  visual_prompt=footage),
            _shot("talking_head", 4, dialogue=intro, description="Presenter introduces the listing"),
            _shot(overview if land else "property_interior", 3, on_screen_text=area,
                  description="Key space of the listing", visual_prompt=footage),
            _shot("cta", 2, on_screen_text=ph("property.price"), dialogue=t["cta"],
                  description="Call to action"),
        ]  # fmt: skip
        title, hook = (
            (t["title_property"] if "property.title" in facts else t["title_social"]),
            t["hook_property"],
        )
    elif "product.name" in facts:
        feature = t["talking_feature"] if "product.feature_1" in facts else ""
        shots = [
            _shot("hook", 2, on_screen_text=ph("product.name"), dialogue=t["hook"],
                  description="Attention-grabbing opener", visual_prompt="lifestyle scene, soft daylight"),
            _shot("product_closeup", 3, on_screen_text=ph("product.feature_1"),
                  description="Original product close-up (composited)"),
            _shot("talking_head", 4, dialogue=f"{t['talking_product']} {feature}".strip(),
                  description="Presenter talks about the product"),
            _shot("cta", 2, on_screen_text=ph("product.price"), dialogue=ph("product.cta") or t["cta"],
                  description="Call to action"),
        ]  # fmt: skip
        title, hook = t["title"], t["hook"]
    else:
        shots = [
            _shot(
                "hook", 2, dialogue=t["hook"], description="Opener", visual_prompt="lifestyle scene, daylight"
            ),
            _shot("talking_head", 5, dialogue=t["talking_social"], description="Presenter speaks to camera"),
            _shot(
                "broll", 3, description="Supporting b-roll", visual_prompt="lifestyle b-roll, natural light"
            ),
            _shot("cta", 2, dialogue=t["cta"], description="Call to action"),
        ]
        title, hook = t["title_social"], t["hook"]
    return normalize_durations(ScriptDraft(title=title, hook=hook, cta=t["cta"], shots=shots), ctx.duration_s)


# --------------------------------------------------------------------------- engine


class ScriptEngine:
    def __init__(
        self, ctx: ScriptContext, llm: LLMProvider | None, check_cancel: Callable[[], None] | None = None
    ):
        self.ctx = ctx
        self.llm = llm
        self.check_cancel = check_cancel or (lambda: None)

    def _prompts(self) -> tuple[str, str]:
        templates = load_templates("script")
        values = {
            "language_name": LANGUAGE_NAMES.get(self.ctx.language[:2], self.ctx.language),
            "project_type": self.ctx.project_type.value,
            "platform": self.ctx.platform,
            "duration": str(self.ctx.duration_s),
            "tone": self.ctx.tone,
            "aspect_ratio": self.ctx.aspect_ratio,
            "shot_types": ", ".join(self.ctx.allowed_types),
            "presenter": self.ctx.presenter or "an adult presenter",
            "facts": self.ctx.facts.prompt_lines(),
            "brief": self.ctx.brief or "(none)",
        }
        return fill(templates["system"], values), fill(templates["user"], values)

    def _evaluate(self, raw: dict[str, Any]) -> tuple[ScriptDraft | None, list[str]]:
        try:
            draft = ScriptDraft.model_validate(raw)
        except ValidationError as exc:
            return None, [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:12]]
        draft = normalize_durations(draft, self.ctx.duration_s)
        errors = structural_errors(draft, self.ctx)
        errors += [
            f"{v.field}: {v.message} (found '{v.found}')"
            for v in fact_guard.check(draft, self.ctx.facts, property_project=self.ctx.is_property)
        ]
        return draft, errors

    def run(self) -> ScriptResult:
        attempts: list[dict[str, Any]] = []
        model_key = self.llm.key if self.llm else None
        if self.llm is not None:
            system, user = self._prompts()
            schema = llm_schema()
            previous: dict[str, Any] | None = None
            errors: list[str] = []
            for attempt in range(1, MAX_ATTEMPTS + 1):
                self.check_cancel()
                prompt = user
                if previous is not None:
                    prompt = (
                        user
                        + "\n\n"
                        + fill(
                            load_templates("script")["repair"],
                            {
                                "errors": "\n".join(f"- {e}" for e in errors),
                                "previous": json.dumps(previous, ensure_ascii=False),
                            },
                        )
                    )
                try:
                    raw = self.llm.generate_json(system, prompt, schema)
                except AppError as exc:  # job cancellation is not an AppError and propagates
                    attempts.append({"attempt": attempt, "ok": False, "errors": [exc.message]})
                    logger.warning("script_llm_error", extra={"code": exc.code.value})
                    break  # server/model problem: repeating will not help
                draft, errors = self._evaluate(raw)
                attempts.append(
                    {"attempt": attempt, "ok": not errors and draft is not None, "errors": errors}
                )
                if draft is not None and not errors:
                    return ScriptResult(
                        render_draft(draft, self.ctx.facts), draft, "llm", model_key, attempts,
                        used_placeholders(draft, self.ctx.facts),
                    )  # fmt: skip
                previous = raw
        draft = template_script(self.ctx)
        if leftover := fact_guard.check(draft, self.ctx.facts, property_project=self.ctx.is_property):
            raise GenerationFailedError(f"Template script failed its own fact check: {leftover[0].message}")
        return ScriptResult(
            render_draft(draft, self.ctx.facts), draft, "template", model_key, attempts,
            used_placeholders(draft, self.ctx.facts),
        )  # fmt: skip
