"""Ollama (https://github.com/ollama/ollama/blob/main/docs/api.md), verified against the API docs:

`POST /api/chat {model, messages, stream: false, format: <JSON schema>, options, keep_alive, think}` →
`{"message": {"content": "<json>"}}`; `GET /api/tags` lists local models; `keep_alive: 0` unloads the
model right after the request so the GPU is free for image/video models.
"""

from __future__ import annotations

from typing import Any

from app.core.config import PerformanceProfile
from app.core.errors import GenerationFailedError, ModelMissingError
from app.providers.base import Availability, LLMCapabilities, LLMProvider, ProviderStatus
from app.providers.device import DeviceInfo
from app.providers.llm.http import parse_json_content, request_json, require_loopback

DEFAULT_URL = "http://127.0.0.1:11434"


class OllamaProvider(LLMProvider):
    @property
    def base_url(self) -> str:
        return require_loopback(str(self.spec.option("base_url", DEFAULT_URL)))

    @property
    def model(self) -> str:
        return str(self.spec.option("model", ""))

    def _tags(self, timeout: float) -> list[str]:
        status, payload = request_json("GET", f"{self.base_url}/api/tags", timeout=timeout)
        if status != 200 or not isinstance(payload, dict):
            raise GenerationFailedError(f"Ollama /api/tags returned HTTP {status}.")
        names = []
        for entry in payload.get("models") or []:
            if isinstance(entry, dict):
                names += [str(entry.get(k)) for k in ("name", "model") if entry.get(k)]
        return names

    def availability(self) -> Availability:
        if not self.model:
            return Availability(ProviderStatus.MODEL_MISSING, "Set `model` (an Ollama tag) in models.yaml.")
        try:
            tags = self._tags(timeout=1.5)
        except Exception:  # any failure means "not running" for the status page
            return Availability(
                ProviderStatus.NOT_INSTALLED,
                f"Ollama is not running at {self.spec.option('base_url', DEFAULT_URL)}.",
            )
        wanted = {self.model, f"{self.model}:latest"}
        if wanted & set(tags):
            return Availability(ProviderStatus.AVAILABLE)
        return Availability(ProviderStatus.MODEL_MISSING, f"Run `ollama pull {self.model}`.")

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            json_schema_output=True, languages=tuple(self.spec.option("languages", ("tr", "en")))
        )

    def load(self, device: DeviceInfo, profile: PerformanceProfile) -> None:
        tags = set(self._tags(timeout=5))
        if not {self.model, f"{self.model}:latest"} & tags:
            raise ModelMissingError(
                f"Ollama model '{self.model}' is not pulled. Run `ollama pull {self.model}`."
            )
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "format": schema,
            "options": {"temperature": float(self.spec.option("temperature", 0.4))},
            "keep_alive": self.spec.option("keep_alive", 0),
        }
        if self.spec.option("think") is not None:
            body["think"] = self.spec.option("think")
        status, payload = request_json(
            "POST", f"{self.base_url}/api/chat", body, timeout=float(self.spec.option("timeout_s", 300))
        )
        if status != 200 or not isinstance(payload, dict):
            message = payload.get("error") if isinstance(payload, dict) else None
            raise GenerationFailedError(f"Ollama returned HTTP {status}: {message or 'no details'}.")
        message = payload.get("message")
        return parse_json_content(message.get("content") if isinstance(message, dict) else None)
