"""Template loading and safe formatting shared by all prompt builders."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import BACKEND_DIR

PROMPTS_DIR = BACKEND_DIR / "config" / "prompts"
_SPACES = re.compile(r"\s+")
_EMPTY_PUNCT = re.compile(r"\s+([.,;:])")
_DOUBLE_PUNCT = re.compile(r"([.,;:])(?:\s*[.,;:])+")


class _Blank(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


@lru_cache(maxsize=8)
def load_templates(name: str, directory: Path = PROMPTS_DIR) -> dict[str, Any]:
    with (directory / f"{name}.yaml").open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{name}.yaml must contain a mapping")
    return data


def render(template: str, values: dict[str, str]) -> str:
    """Fill {placeholders}; user values are inserted verbatim (never re-parsed as templates)."""
    text = template.format_map(_Blank(values))
    text = _SPACES.sub(" ", text).strip()
    text = _EMPTY_PUNCT.sub(r"\1", text)
    text = _DOUBLE_PUNCT.sub(lambda m: m.group(0)[-1], text)  # keep the strongest (last) mark
    return text.strip(" ,;")


def join_nonempty(parts: list[str], sep: str = ", ") -> str:
    return sep.join(p.strip().rstrip(".") for p in parts if p and p.strip())
