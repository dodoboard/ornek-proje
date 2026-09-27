"""Content guards applied to user-provided character descriptions.

The studio is for adult characters only. This is a coarse keyword guard, not a classifier:
it blocks obvious references to minors in EN/TR so they never reach a prompt.
"""

from __future__ import annotations

import re

_MINOR_PATTERNS = (
    r"child(?:ren|like|ish)?",
    r"kids?",
    r"minors?",
    r"under[\s-]?age",
    r"(?:pre)?teens?",
    r"teenager?s?",
    r"adolescents?",
    r"school\s?(?:girl|boy)s?",
    r"lol(?:i|ita)",
    r"shota",
    r"infants?",
    r"toddlers?",
    r"(?:1[0-7]|[1-9])[\s-]?(?:yo|y/o|years?[\s-]old)",
    # Turkish
    r"çocuk\w*",
    r"ergen\w*",
    r"reşit\s+olmayan",
    r"küçük\s+(?:kız|erkek|çocuk)",
    r"(?:ilkokul|ortaokul|lise)\s*(?:öğrencisi|li)\w*",
    r"(?:1[0-7]|[1-9])\s*yaşında\w*",
)

_MINOR_RE = re.compile(r"(?<!\w)(?:" + "|".join(_MINOR_PATTERNS) + r")(?!\w)", re.IGNORECASE)


def find_minor_reference(text: str) -> str | None:
    match = _MINOR_RE.search(text)
    return match.group(0) if match else None
