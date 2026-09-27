"""LLM providers against a real local HTTP stub that mimics the documented Ollama / llama-server APIs."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

from app.core.config import PerformanceProfile, Settings
from app.core.errors import GenerationFailedError, ModelMissingError, ProviderUnavailableError
from app.providers.base import ProviderStatus
from app.providers.catalog import ModelSpec
from app.providers.device import DeviceInfo
from app.providers.llm.fake import PLACEHOLDER, example_for
from app.providers.llm.http import is_loopback_url
from app.providers.llm.llamacpp_server import LlamaCppServerProvider
from app.providers.llm.ollama import OllamaProvider

CPU = DeviceInfo(device="cpu", dtype="float32")
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}


class _Stub(BaseHTTPRequestHandler):
    requests: ClassVar[list[tuple[str, str, Any]]] = []
    responses: ClassVar[dict[tuple[str, str], tuple[int, Any]]] = {}

    def _reply(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        _Stub.requests.append((method, self.path, body))
        status, payload = _Stub.responses.get((method, self.path), (404, {"error": "not found"}))
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._reply("GET")

    def do_POST(self) -> None:
        self._reply("POST")

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    _Stub.requests = []
    _Stub.responses = {}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _ollama(settings: Settings, url: str, **extra: Any) -> OllamaProvider:
    spec = ModelSpec(provider="ollama", base_url=url, model="qwen3:8b", think=False, keep_alive=0, **extra)
    return OllamaProvider("ollama_default", spec, settings)


def test_ollama_status_and_structured_chat(settings: Settings, server: str) -> None:
    provider = _ollama(settings, server)
    _Stub.responses[("GET", "/api/tags")] = (200, {"models": [{"name": "llama3.2:latest"}]})
    assert provider.availability().status is ProviderStatus.MODEL_MISSING
    with pytest.raises(ModelMissingError, match="ollama pull qwen3:8b"):
        provider.load(CPU, PerformanceProfile.BALANCED)

    _Stub.responses[("GET", "/api/tags")] = (200, {"models": [{"name": "qwen3:8b", "model": "qwen3:8b"}]})
    assert provider.availability().status is ProviderStatus.AVAILABLE
    provider.load(CPU, PerformanceProfile.BALANCED)
    _Stub.responses[("POST", "/api/chat")] = (
        200,
        {"message": {"role": "assistant", "content": '{"title": "Merhaba"}'}},
    )
    assert provider.generate_json("sys", "user", SCHEMA) == {"title": "Merhaba"}
    method, path, body = _Stub.requests[-1]
    assert (method, path) == ("POST", "/api/chat")
    assert body["format"] == SCHEMA and body["stream"] is False and body["keep_alive"] == 0
    assert body["think"] is False and body["model"] == "qwen3:8b"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_ollama_bad_output_and_server_down(settings: Settings, server: str) -> None:
    provider = _ollama(settings, server)
    _Stub.responses[("POST", "/api/chat")] = (200, {"message": {"content": "not json"}})
    with pytest.raises(GenerationFailedError, match="not valid JSON"):
        provider.generate_json("s", "u", SCHEMA)
    _Stub.responses[("POST", "/api/chat")] = (500, {"error": "model crashed"})
    with pytest.raises(GenerationFailedError, match="model crashed"):
        provider.generate_json("s", "u", SCHEMA)
    down = _ollama(settings, "http://127.0.0.1:9")
    assert down.availability().status is ProviderStatus.NOT_INSTALLED
    with pytest.raises(ProviderUnavailableError, match="not reachable"):
        down.generate_json("s", "u", SCHEMA)


def test_remote_urls_are_refused(settings: Settings) -> None:
    assert is_loopback_url("http://localhost:11434") and is_loopback_url("http://[::1]:8080")
    assert not is_loopback_url("http://192.168.1.5:11434") and not is_loopback_url("file:///etc/passwd")
    provider = _ollama(settings, "https://api.example.com")
    with pytest.raises(ProviderUnavailableError, match="loopback"):
        provider.generate_json("s", "u", SCHEMA)


def test_llamacpp_server_contract(settings: Settings, server: str) -> None:
    provider = LlamaCppServerProvider(
        "llamacpp_local", ModelSpec(provider="llamacpp_server", base_url=server), settings
    )
    _Stub.responses[("GET", "/health")] = (503, {"error": {"code": 503, "message": "Loading model"}})
    assert provider.availability().status is ProviderStatus.MODEL_MISSING
    _Stub.responses[("GET", "/health")] = (200, {"status": "ok"})
    assert provider.availability().status is ProviderStatus.AVAILABLE
    _Stub.responses[("POST", "/v1/chat/completions")] = (
        200,
        {"choices": [{"message": {"role": "assistant", "content": '{"title": "Hi"}'}}]},
    )
    assert provider.generate_json("s", "u", SCHEMA) == {"title": "Hi"}
    body = _Stub.requests[-1][2]
    assert body["response_format"] == {"type": "json_object", "schema": SCHEMA}


def test_fake_llm_builds_schema_instances() -> None:
    schema = {
        "type": "object",
        "required": ["items", "mode", "n"],
        "properties": {
            "items": {"type": "array", "minItems": 2, "items": {"$ref": "#/$defs/Item"}},
            "mode": {"enum": ["a", "b"]},
            "n": {"type": "integer", "minimum": 3},
        },
        "$defs": {"Item": {"type": "object", "properties": {"t": {"type": "string"}}, "required": ["t"]}},
    }
    assert example_for(schema) == {"items": [{"t": PLACEHOLDER}, {"t": PLACEHOLDER}], "mode": "a", "n": 3}
