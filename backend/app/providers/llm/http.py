"""Minimal JSON-over-HTTP client for local LLM servers (stdlib only; loopback hosts only)."""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from app.core.errors import GenerationFailedError, ProviderUnavailableError


def is_loopback_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    if parts.hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(parts.hostname).is_loopback
    except ValueError:
        return False


def require_loopback(url: str) -> str:
    """Scripts and product facts never leave the machine: only 127.0.0.1/::1/localhost are accepted."""
    if not is_loopback_url(url):
        raise ProviderUnavailableError(f"LLM server URL must be a local loopback address, got '{url}'.")
    return url.rstrip("/")


def request_json(
    method: str, url: str, body: dict[str, Any] | None = None, timeout: float = 120.0
) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(  # noqa: S310 - URL is validated by require_loopback
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        parts = urlsplit(url)
        raise ProviderUnavailableError(
            f"Local LLM server not reachable at {parts.scheme}://{parts.netloc}."
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GenerationFailedError("The LLM server returned a non-JSON response.") from exc
    return status, payload


def parse_json_content(content: object) -> dict[str, Any]:
    """The model's message content must itself be a JSON object."""
    if not isinstance(content, str):
        raise GenerationFailedError("The LLM returned no text content.")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise GenerationFailedError("The LLM output was not valid JSON.") from exc
    if not isinstance(value, dict):
        raise GenerationFailedError("The LLM output was not a JSON object.")
    return value
