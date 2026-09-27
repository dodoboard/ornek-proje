"""DEV/TEST ONLY placeholder LLM: returns the smallest JSON object that satisfies the given schema.

It never writes real copy; every string is a visible placeholder so it cannot be mistaken for a script.
"""

from __future__ import annotations

from typing import Any

from app.core.config import PerformanceProfile
from app.providers.base import Availability, LLMCapabilities, LLMProvider, Maturity, ProviderStatus
from app.providers.device import DeviceInfo

PLACEHOLDER = "DEV PLACEHOLDER"


def example_for(schema: dict[str, Any], defs: dict[str, Any] | None = None) -> Any:
    """Build a minimal instance of a (pydantic-generated) JSON schema."""
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return example_for(defs[schema["$ref"].split("/")[-1]], defs)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [o for o in schema[key] if o.get("type") != "null"] or schema[key]
            return example_for(options[0], defs)
    kind = schema.get("type")
    if kind == "object":
        props = schema.get("properties", {})
        return {name: example_for(prop, defs) for name, prop in props.items()}  # optional fields too
    if kind == "array":
        count = max(1, int(schema.get("minItems", 1)))
        return [example_for(schema.get("items", {}), defs) for _ in range(count)]
    if kind == "integer":
        return int(schema.get("minimum", schema.get("exclusiveMinimum", 0)))
    if kind == "number":
        return float(schema.get("minimum", 1.0))
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    text = PLACEHOLDER
    return text[: schema.get("maxLength", len(text))] if schema.get("maxLength") else text


class FakeLLMProvider(LLMProvider):
    maturity = Maturity.DEV_ONLY

    def availability(self) -> Availability:
        return Availability(
            ProviderStatus.AVAILABLE, "Development placeholder; returns schema-shaped dummy JSON."
        )

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(json_schema_output=True, languages=("tr", "en"))

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        value = example_for(schema)
        assert isinstance(value, dict)
        return value
