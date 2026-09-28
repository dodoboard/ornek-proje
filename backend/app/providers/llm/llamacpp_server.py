"""llama.cpp `llama-server` (tools/server/README.md), verified against its README:

`GET /health` → 200 `{"status": "ok"}` when the model is loaded (503 while loading);
`POST /v1/chat/completions` with `response_format: {"type": "json_object", "schema": {...}}` for
schema-constrained output; the answer is in `choices[0].message.content`.
"""

from __future__ import annotations

from typing import Any

from app.core.config import PerformanceProfile
from app.core.errors import GenerationFailedError, ProviderUnavailableError
from app.providers.base import Availability, LLMCapabilities, LLMProvider, ProviderStatus
from app.providers.device import DeviceInfo
from app.providers.llm.http import parse_json_content, request_json, require_loopback

DEFAULT_URL = "http://127.0.0.1:8080"


class LlamaCppServerProvider(LLMProvider):
    @property
    def base_url(self) -> str:
        return require_loopback(str(self.spec.option("base_url", DEFAULT_URL)))

    def _health(self, timeout: float) -> int:
        status, _ = request_json("GET", f"{self.base_url}/health", timeout=timeout)
        return status

    def availability(self) -> Availability:
        try:
            status = self._health(timeout=1.5)
        except Exception:  # any failure means "not running" for the status page
            return Availability(
                ProviderStatus.NOT_INSTALLED,
                f"llama-server is not running at {self.spec.option('base_url', DEFAULT_URL)}.",
            )
        if status == 200:
            return Availability(ProviderStatus.AVAILABLE)
        return Availability(ProviderStatus.MODEL_MISSING, f"llama-server is not ready (HTTP {status}).")

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            json_schema_output=True, languages=tuple(self.spec.option("languages", ("tr", "en")))
        )

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        if self._health(timeout=5) != 200:
            raise ProviderUnavailableError("llama-server is not ready yet (model still loading?).")
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": float(self.spec.option("temperature", 0.4)),
            "response_format": {"type": "json_object", "schema": schema},
            "stream": False,
        }
        if model := self.spec.option("model"):
            body["model"] = model
        status, payload = request_json(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            body,
            timeout=float(self.spec.option("timeout_s", 300)),
        )
        if status != 200 or not isinstance(payload, dict):
            raise GenerationFailedError(f"llama-server returned HTTP {status}.")
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GenerationFailedError("llama-server response had no message content.") from exc
        return parse_json_content(content)
