from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.core.errors import ProviderUnavailableError
from app.models.enums import ProjectType
from app.schemas.script import ScriptDraft
from app.services import fact_guard
from app.services.facts import FactSheet, format_number, format_price
from app.services.script_engine import ScriptContext, ScriptEngine, normalize_durations


def product_facts() -> FactSheet:
    sheet = FactSheet(language="tr")
    sheet.add("product.name", "Aurora Serum 30ml", "product name")
    sheet.add("product.price", format_price(Decimal("1299.00"), "TRY", "tr"), "price")
    sheet.add("product.feature_1", "Hyaluronik asit içerir", "verified feature")
    return sheet


def land_facts() -> FactSheet:
    sheet = FactSheet(language="tr")
    sheet.add("property.title", "Deniz manzaralı arsa", "title")
    sheet.add("property.land_sqm", f"{format_number(1250.5, 'tr')} m²", "land area")
    return sheet


def ctx(facts: FactSheet, kind: ProjectType = ProjectType.PRODUCT_AD, brief: str = "") -> ScriptContext:
    return ScriptContext(kind, "tr", "instagram", 15, "friendly", "9:16", "Deniz, 28", brief, facts)


def draft(**shot: Any) -> dict[str, Any]:
    base = {"type": "talking_head", "duration_s": 5, "dialogue": "{{product.name}} ile tanışın."}
    return {
        "title": "{{product.name}}",
        "hook": "Yeni rutinim",
        "shots": [{**base, **shot}, {"type": "cta", "duration_s": 5, "on_screen_text": "{{product.price}}"}],
        "cta": "Şimdi deneyin",
    }


class ScriptedLLM:
    key = "scripted"

    def __init__(self, *outputs: dict[str, Any] | Exception) -> None:
        self.outputs = list(outputs)
        self.calls: list[str] = []

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(user)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def test_formatting_is_locale_aware() -> None:
    assert format_price(Decimal("1250000.50"), "TRY", "tr") == "1.250.000,50 TRY"
    assert format_price(Decimal("1299.00"), "USD", "en") == "1,299 USD"
    sheet = product_facts()
    assert sheet.render("{{product.price}} / {{nope}}") == ("1.299 TRY / {{nope}}", ["nope"])


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("Sadece 999 TL!", "typed_number"),
        ("Fiyatı ₺ ile öde", "typed_unit"),
        ("Klinik olarak kanıtlandı", "unverified_claim"),
        ("{{product.discount}} indirim", "unknown_placeholder"),
    ],
)
def test_fact_guard_flags_invented_facts(text: str, rule: str) -> None:
    violations = fact_guard.check(
        ScriptDraft.model_validate(draft(dialogue=text)), product_facts(), property_project=False
    )
    assert rule in {v.rule for v in violations}


def test_fact_guard_accepts_placeholders_and_verified_wording() -> None:
    ok = ScriptDraft.model_validate(draft(dialogue="{{product.name}}: {{product.feature_1}}, 30ml şişe."))
    assert fact_guard.check(ok, product_facts(), property_project=False) == []
    # A claim the user wrote in the brief is verified input.
    sheet = product_facts()
    sheet.verified_text.append("Dermatolog onaylı formül")
    claim = ScriptDraft.model_validate(draft(dialogue="Dermatolog onaylı bir formül."))
    assert fact_guard.check(claim, sheet, property_project=False) == []


def test_land_terms_need_a_verified_fact() -> None:
    text = ScriptDraft.model_validate(
        {"title": "{{property.title}}", "hook": "Arsa", "shots": [
            {"type": "land_overview", "duration_s": 5, "dialogue": "İmarlı, elektriği hazır."},
            {"type": "cta", "duration_s": 5, "on_screen_text": "{{property.land_sqm}}"}]}
    )  # fmt: skip
    violations = fact_guard.check(text, land_facts(), property_project=True)
    assert {v.found for v in violations} == {"İmarlı", "elektriği"}
    assert {v.rule for v in violations} == {"missing_fact"}


def test_valid_llm_script_is_rendered_and_normalised() -> None:
    llm = ScriptedLLM(draft())
    result = ScriptEngine(ctx(product_facts()), llm).run()  # type: ignore[arg-type]
    assert result.source == "llm" and len(llm.calls) == 1
    assert result.draft.title == "Aurora Serum 30ml"
    assert result.draft.shots[1].on_screen_text == "1.299 TRY"
    assert result.raw.shots[1].on_screen_text == "{{product.price}}"
    assert sum(s.duration_s for s in result.draft.shots) == 15
    assert result.placeholders == ["product.name", "product.price"]


def test_invented_fact_is_repaired_once() -> None:
    llm = ScriptedLLM(draft(dialogue="Sadece 999 TL!"), draft())
    result = ScriptEngine(ctx(product_facts()), llm).run()  # type: ignore[arg-type]
    assert result.source == "llm"
    assert [a["ok"] for a in result.attempts] == [False, True]
    assert "999" in llm.calls[1] and "rejected" in llm.calls[1]


def test_falls_back_to_template_after_two_failures_or_server_error() -> None:
    bad = ScriptedLLM(draft(type="property_exterior"), {"title": "x"})
    result = ScriptEngine(ctx(product_facts()), bad).run()  # type: ignore[arg-type]
    assert result.source == "template" and len(result.attempts) == 2
    assert "not allowed" in result.attempts[0]["errors"][0]

    down = ScriptedLLM(ProviderUnavailableError("Local LLM server not reachable."))
    result = ScriptEngine(ctx(product_facts()), down).run()  # type: ignore[arg-type]
    assert result.source == "template"
    assert result.attempts == [{"attempt": 1, "ok": False, "errors": ["Local LLM server not reachable."]}]


@pytest.mark.parametrize(
    "kind", [ProjectType.PRODUCT_AD, ProjectType.SOCIAL, ProjectType.LAND, ProjectType.REAL_ESTATE]
)
def test_template_uses_only_verified_facts(kind: ProjectType) -> None:
    facts = land_facts() if kind in (ProjectType.LAND, ProjectType.REAL_ESTATE) else product_facts()
    if kind is ProjectType.SOCIAL:
        facts = FactSheet(language="en")
    result = ScriptEngine(ctx(facts, kind), None).run()
    assert result.source == "template"
    assert (
        fact_guard.check(
            result.raw, facts, property_project=kind in (ProjectType.LAND, ProjectType.REAL_ESTATE)
        )
        == []
    )
    assert sum(s.duration_s for s in result.draft.shots) == 15
    assert "{{" not in result.draft.model_dump_json()


def test_normalize_durations_keeps_minimum() -> None:
    d = ScriptDraft.model_validate(draft())
    assert [s.duration_s for s in normalize_durations(d, 30).shots] == [15, 15]
    assert all(s.duration_s >= 1 for s in normalize_durations(d, 1).shots)
