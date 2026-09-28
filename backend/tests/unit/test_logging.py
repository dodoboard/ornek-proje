from __future__ import annotations

import json
import logging

from app.core.logging import ContextFilter, JsonFormatter, request_id_var


def test_json_formatter_includes_context_and_extra() -> None:
    token = request_id_var.set("req-1")
    try:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        record.stage = "encoding"
        ContextFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["msg"] == "hello world"
    assert payload["request_id"] == "req-1"
    assert payload["stage"] == "encoding"
    assert "job_id" not in payload
