"""Prefixed, time-sortable identifiers (ULID layout: 48-bit ms timestamp + 80-bit randomness)."""

from __future__ import annotations

import re
import secrets
import time
from enum import StrEnum

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LENGTH = 26
_ULID_RE = re.compile(rf"^[{_CROCKFORD}]{{{_ULID_LENGTH}}}$")


class IdPrefix(StrEnum):
    CHARACTER = "CHR"
    PRODUCT = "PRD"
    PROPERTY = "PRP"
    PROJECT = "PRJ"
    STORYBOARD = "SB"
    SHOT = "SHT"
    SCRIPT = "SCR"
    JOB = "JOB"
    ASSET = "AST"
    OUTPUT = "OUT"
    GENERATION = "GEN"
    VOICE = "VOC"
    CONSENT = "CNS"
    TIMELINE = "TL"
    WORKER = "WRK"


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        value, remainder = divmod(value, 32)
        chars.append(_CROCKFORD[remainder])
    return "".join(reversed(chars))


def new_ulid(timestamp_ms: int | None = None) -> str:
    ts = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    if not 0 <= ts < 2**48:
        raise ValueError("timestamp out of ULID range")
    return _encode((ts << 80) | secrets.randbits(80), _ULID_LENGTH)


def new_id(prefix: IdPrefix) -> str:
    return f"{prefix.value}_{new_ulid()}"


def is_valid_id(value: str, prefix: IdPrefix) -> bool:
    head, sep, tail = value.partition("_")
    return sep == "_" and head == prefix.value and bool(_ULID_RE.match(tail))
