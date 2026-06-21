"""Focused safe-metric and OTLP configuration checks."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.config import AppSettings
from app.core.observability import get_telemetry, inject_trace_headers, metrics_payload
from app.services.evaluation.dispatch import CeleryEvaluationTaskDispatcher
from app.workers import tasks
from opentelemetry.sdk.trace import TracerProvider
from pydantic import ValidationError


def test_metrics_payload_declares_all_startup_guaranteed_metric_families() -> None:
    payload = metrics_payload().decode("utf-8")

    assert "# HELP nordic_api_http_requests_total" in payload
    assert "# HELP nordic_workflow_runs_total" in payload
    assert "# HELP nordic_model_request_duration_seconds" in payload
    assert "organization_id" not in payload
    assert "case_id" not in payload


def test_api_metric_uses_only_bounded_labels() -> None:
    get_telemetry().api_request(
        method="GET", route="/api/cases/{case_id}", status_code=200, duration_ms=12.5
    )

    payload = metrics_payload().decode("utf-8")
    assert 'method="GET"' in payload
    assert 'route="/api/cases/{case_id}"' in payload
    assert 'status_class="2xx"' in payload
    assert "request_id" not in payload


def test_refusal_metric_records_only_a_closed_reason() -> None:
    get_telemetry().rag_refusal(reason="insufficient_evidence")

    payload = metrics_payload().decode("utf-8")
    assert 'reason="insufficient_evidence"' in payload
    assert "question" not in payload


def test_otlp_endpoint_is_optional_and_must_be_http() -> None:
    assert AppSettings().otlp_endpoint is None
    assert AppSettings(otlp_endpoint="https://collector.internal/").otlp_endpoint == (
        "https://collector.internal"
    )
    with pytest.raises(ValidationError, match="otlp_endpoint"):
        AppSettings(otlp_endpoint="collector.internal")


def test_trace_propagation_uses_only_w3c_headers() -> None:
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("request"):
        headers = inject_trace_headers()

    assert set(headers) == {"traceparent"}
    assert headers["traceparent"].startswith("00-")


def test_celery_dispatch_keeps_the_uuid_body_and_uses_metadata_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def apply_async(**kwargs: object) -> None:
        observed.update(kwargs)

    monkeypatch.setattr(tasks.run_evaluation_task, "apply_async", apply_async)
    run_id = uuid4()
    CeleryEvaluationTaskDispatcher().dispatch_evaluation(run_id)

    assert observed["args"] == [str(run_id)]
    headers = observed["headers"]
    assert isinstance(headers, dict)
    assert set(headers) <= {"traceparent", "tracestate"}
