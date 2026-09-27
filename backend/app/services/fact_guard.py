"""FactGuard: rejects script text that states facts the user did not provide.

Checked on the model's draft *before* placeholders are filled, on audience-facing text (title, hook,
dialogue, on-screen text, CTA). A fact may only enter through a {{placeholder}}; typed numbers,
currencies, units, land/zoning claims and unverifiable marketing claims are violations unless the
same wording already exists in the user's verified input.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.schemas.script import ScriptDraft
from app.services.facts import PLACEHOLDER_RE, FactSheet

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_UNIT_PATTERNS = (
    r"₺", r"\$", r"€", r"£", r"\bTL\b", r"\bTRY\b", r"\bUSD\b", r"\bEUR\b", r"\bGBP\b",
    r"m²", r"\bm2\b", r"metrekare", r"\bsqm\b", r"square\s+met(?:er|re)s?", r"\bdönüm\w*", r"\bacres?\b",
)  # fmt: skip
_UNIT_RE = re.compile("|".join(_UNIT_PATTERNS), re.IGNORECASE)

#: Land/real-estate claims that need a verified fact (key) before they may be mentioned at all.
_FACT_TERMS: dict[str, tuple[str, ...]] = {
    "property.zoning": (r"imar\w*", r"zon(?:ing|ed)"),
    "property.parcel": (r"parsel\w*", r"\bada\b", r"tapu\w*", r"parcel\w*", r"title\s+deed"),
    "property.road_access": (r"yola\s+cephe\w*", r"road\s+(?:access|frontage)"),
    "property.electricity": (r"elektri\w*", r"electricity"),
    "property.water": (r"\bsu\b", r"\bsuyu\b", r"\bwater\b"),
    "property.location": (r"(?:koordinat|coordinates?)\w*",),
}
#: Claims we can never verify from a product sheet unless the user wrote them.
_CLAIM_TERMS = (
    r"garanti\w*", r"guarantee\w*", r"klini\w*", r"clinical\w*", r"dermatolog\w*", r"\bFDA\b",
    r"onaylı", r"certified", r"sertifika\w*", r"#\s?1\b", r"number\s+one", r"best[\s-]?selling",
    r"en\s+çok\s+satan", r"ödüllü", r"award[\s-]?winning", r"\bcure\w*", r"tedavi\s+eder",
)  # fmt: skip
_CLAIM_RE = re.compile("|".join(_CLAIM_TERMS), re.IGNORECASE)


@dataclass(frozen=True)
class Violation:
    field: str
    rule: str
    found: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def audience_fields(draft: ScriptDraft) -> list[tuple[str, str]]:
    fields = [("title", draft.title), ("hook", draft.hook), ("cta", draft.cta)]
    for i, shot in enumerate(draft.shots):
        fields += [
            (f"shots[{i}].dialogue", shot.dialogue),
            (f"shots[{i}].on_screen_text", shot.on_screen_text),
        ]
    return [(name, text) for name, text in fields if text]


def all_fields(draft: ScriptDraft) -> list[tuple[str, str]]:
    fields = audience_fields(draft)
    for i, shot in enumerate(draft.shots):
        fields += [
            (f"shots[{i}].description", shot.description),
            (f"shots[{i}].visual_prompt", shot.visual_prompt),
        ]
    return fields


def _verified_blob(facts: FactSheet) -> str:
    return "\n".join([*facts.values.values(), *facts.verified_text]).casefold()


def check(draft: ScriptDraft, facts: FactSheet, *, property_project: bool) -> list[Violation]:
    violations: list[Violation] = []
    verified = _verified_blob(facts)
    allowed_numbers = set(_NUMBER_RE.findall(verified))

    for name, text in all_fields(draft):
        _, unknown = facts.render(text)
        violations += [
            Violation(
                name, "unknown_placeholder", f"{{{{{k}}}}}", f"'{k}' is not a verified fact of this project."
            )
            for k in unknown
        ]

    for name, text in audience_fields(draft):
        bare = PLACEHOLDER_RE.sub(" ", text)
        for number in _NUMBER_RE.findall(bare):
            if number not in allowed_numbers:
                violations.append(
                    Violation(name, "typed_number", number, "Numbers must come from a {{placeholder}}.")
                )
        for match in _UNIT_RE.finditer(bare):
            if match.group(0).casefold() not in verified:
                violations.append(
                    Violation(
                        name, "typed_unit", match.group(0), "Prices/units must come from a {{placeholder}}."
                    )
                )
        for match in _CLAIM_RE.finditer(bare):
            if match.group(0).casefold() not in verified:
                violations.append(
                    Violation(
                        name, "unverified_claim", match.group(0), "This claim is not in the verified input."
                    )
                )
        if property_project:
            for key, patterns in _FACT_TERMS.items():
                if key in facts.values:
                    continue
                for pattern in patterns:
                    if found := re.search(pattern, bare, re.IGNORECASE):
                        violations.append(
                            Violation(
                                name, "missing_fact", found.group(0), f"No verified '{key}' for this listing."
                            )
                        )
    return violations
