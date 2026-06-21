import json
import re

import pytest
from app.core.config import AppSettings
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
    normalize_request_id,
)
from opentelemetry.sdk.trace import TracerProvider

_HEX_32 = re.compile(r"\A[0-9a-f]{32}\Z")


@pytest.fixture(autouse=True)
def _isolate_logging_context() -> None:
    clear_request_context()


def _json_lines(captured: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in captured.splitlines() if line.strip()]


def test_json_logging_includes_only_safe_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(AppSettings(environment="test", log_format="json"))

    get_logger("test.logger").info("event.happened", detail="safe-value")

    lines = _json_lines(capsys.readouterr().out)
    assert len(lines) == 1
    record = lines[0]
    assert record["event"] == "event.happened"
    assert record["service"] == "nordic-regulated-ai-api"
    assert record["environment"] == "test"
    assert record["level"] == "info"
    assert record["detail"] == "safe-value"
    assert "timestamp" in record


def test_configure_logging_is_idempotent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = AppSettings(environment="test", log_format="json")
    configure_logging(settings)
    configure_logging(settings)

    get_logger("test.logger").info("only.once")

    lines = _json_lines(capsys.readouterr().out)
    assert len(lines) == 1


def test_console_logging_is_default(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(AppSettings(environment="test"))

    get_logger("test.logger").info("console.event")

    out = capsys.readouterr().out
    assert "console.event" in out


def test_log_level_filtering(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(AppSettings(environment="test", log_level="warning", log_format="json"))

    logger = get_logger("test.logger")
    logger.info("suppressed.event")
    logger.warning("emitted.event")

    lines = _json_lines(capsys.readouterr().out)
    events = [line["event"] for line in lines]
    assert "suppressed.event" not in events
    assert "emitted.event" in events


def test_request_context_is_bound_and_cleared(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(AppSettings(environment="test", log_format="json"))
    logger = get_logger("test.logger")

    bind_request_context(request_id="abc123")
    logger.info("with.context")
    clear_request_context()
    logger.info("without.context")

    lines = _json_lines(capsys.readouterr().out)
    assert lines[0]["request_id"] == "abc123"
    assert "request_id" not in lines[1]


def test_json_logging_includes_active_generated_trace_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(AppSettings(environment="test", log_format="json"))
    tracer = TracerProvider().get_tracer("test")

    with tracer.start_as_current_span("safe.operation"):
        get_logger("test.logger").info("with.trace")

    record = _json_lines(capsys.readouterr().out)[0]
    assert record["event"] == "with.trace"
    assert len(str(record["trace_id"])) == 32
    assert len(str(record["span_id"])) == 16
    assert "prompt" not in record
    assert "exception" not in record


def test_normalize_request_id_passes_valid_value() -> None:
    assert normalize_request_id("valid-id_1.2", max_length=128) == "valid-id_1.2"


def test_normalize_request_id_generates_when_missing() -> None:
    generated = normalize_request_id(None, max_length=128)
    assert _HEX_32.match(generated)


@pytest.mark.parametrize("raw", ["bad id with spaces", "has/slash", "semi;colon", ""])
def test_normalize_request_id_rejects_unsafe_values(raw: str) -> None:
    generated = normalize_request_id(raw, max_length=128)
    assert _HEX_32.match(generated)
    assert generated != raw


def test_normalize_request_id_rejects_too_long_value() -> None:
    generated = normalize_request_id("a" * 200, max_length=128)
    assert _HEX_32.match(generated)
