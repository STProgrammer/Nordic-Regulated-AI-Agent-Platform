"""Safe metrics and optional OTLP tracing for application-owned operations.

The module deliberately has one bounded label vocabulary and never accepts
tenant identifiers, resource UUIDs, request data, or exception text.  The API
process exposes the Prometheus registry when enabled; worker processes use the
same emitters for local instrumentation and may export trace spans through OTLP.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from decimal import Decimal
from functools import wraps
from time import perf_counter
from typing import Literal, ParamSpec, TypeVar

from opentelemetry import propagate, trace
from opentelemetry.context import attach, detach
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from app.core.config import AppSettings
from app.core.logging import get_logger

_REGISTRY = CollectorRegistry(auto_describe=True)
_TRACING_CONFIGURED = False
TaskResult = TypeVar("TaskResult")
TaskParameters = ParamSpec("TaskParameters")

_API_REQUESTS = Counter(
    "nordic_api_http_requests_total",
    "Completed API HTTP requests.",
    ("method", "route", "status_class"),
    registry=_REGISTRY,
)
_API_DURATION = Histogram(
    "nordic_api_http_request_duration_seconds",
    "Completed API HTTP request duration in seconds.",
    ("method", "route", "status_class"),
    registry=_REGISTRY,
)
_WORKFLOW_RUNS = Counter(
    "nordic_workflow_runs_total",
    "Terminal workflow outcomes.",
    ("workflow_name", "outcome"),
    registry=_REGISTRY,
)
_WORKFLOW_NODE_DURATION = Histogram(
    "nordic_workflow_node_duration_seconds",
    "Workflow node duration in seconds.",
    ("workflow_name", "node_name", "outcome"),
    registry=_REGISTRY,
)
_RETRIEVAL_DURATION = Histogram(
    "nordic_retrieval_duration_seconds",
    "Retrieval operation duration in seconds.",
    ("operation", "outcome"),
    registry=_REGISTRY,
)
_MODEL_DURATION = Histogram(
    "nordic_model_request_duration_seconds",
    "Model request duration in seconds.",
    ("provider", "model", "operation", "outcome"),
    registry=_REGISTRY,
)
_MODEL_TOKENS = Counter(
    "nordic_model_tokens_total",
    "Known model token usage.",
    ("provider", "model", "operation", "kind"),
    registry=_REGISTRY,
)
_MODEL_COST = Counter(
    "nordic_model_estimated_cost_total",
    "Configured estimated model cost in the application's existing price-rate unit.",
    ("provider", "model", "operation"),
    registry=_REGISTRY,
)
_PARSING_FAILURES = Counter(
    "nordic_document_parsing_failures_total",
    "Document parsing failures by controlled category.",
    ("outcome",),
    registry=_REGISTRY,
)
_EVALUATION_CASES = Counter(
    "nordic_evaluation_case_results_total",
    "Deterministic evaluation case outcomes; derive pass rate from these counters.",
    ("outcome",),
    registry=_REGISTRY,
)
_APPROVAL_DECISIONS = Counter(
    "nordic_approval_decisions_total",
    "Recorded human approval decisions.",
    ("decision",),
    registry=_REGISTRY,
)
_RAG_REFUSALS = Counter(
    "nordic_rag_refusals_total",
    "Source-grounded answer refusals by controlled reason.",
    ("reason",),
    registry=_REGISTRY,
)


class Telemetry:
    """One safe, process-local façade shared by API services and worker adapters."""

    def __init__(self) -> None:
        self._tracer = trace.get_tracer("nordic.observability")

    @contextmanager
    def span(
        self, name: str, attributes: Mapping[str, str | int | float] | None = None
    ) -> Iterator[None]:
        """Start an optional internal span without ever recording exception bodies."""

        with self._tracer.start_as_current_span(name) as span:
            if attributes is not None:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield

    def api_request(self, *, method: str, route: str, status_code: int, duration_ms: float) -> None:
        labels = {"method": method, "route": route, "status_class": f"{status_code // 100}xx"}
        _API_REQUESTS.labels(**labels).inc()
        _API_DURATION.labels(**labels).observe(max(0.0, duration_ms) / 1000)

    def workflow_run(self, *, workflow_name: str, outcome: str) -> None:
        _WORKFLOW_RUNS.labels(workflow_name=workflow_name, outcome=outcome).inc()
        get_logger("workflow.telemetry").info(
            "workflow.completed", workflow_name=workflow_name, outcome=outcome
        )

    def workflow_node(
        self, *, workflow_name: str, node_name: str, outcome: str, duration_ms: int
    ) -> None:
        _WORKFLOW_NODE_DURATION.labels(
            workflow_name=workflow_name, node_name=node_name, outcome=outcome
        ).observe(max(0, duration_ms) / 1000)
        get_logger("workflow.telemetry").info(
            "workflow.node_completed",
            workflow_name=workflow_name,
            node_name=node_name,
            outcome=outcome,
            duration_ms=duration_ms,
        )

    def retrieval(self, *, operation: str, outcome: str, duration_ms: int) -> None:
        _RETRIEVAL_DURATION.labels(operation=operation, outcome=outcome).observe(
            max(0, duration_ms) / 1000
        )
        get_logger("retrieval.telemetry").info(
            "retrieval.completed", operation=operation, outcome=outcome, duration_ms=duration_ms
        )

    def model(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        outcome: Literal["success", "failure"],
        latency_ms: int | None,
        token_input: int | None = None,
        token_output: int | None = None,
        cost_estimate: Decimal | None = None,
    ) -> None:
        labels = {
            "provider": provider,
            "model": model,
            "operation": operation,
            "outcome": outcome,
        }
        if latency_ms is not None:
            _MODEL_DURATION.labels(**labels).observe(max(0, latency_ms) / 1000)
        token_labels = {key: value for key, value in labels.items() if key != "outcome"}
        if token_input is not None:
            _MODEL_TOKENS.labels(**token_labels, kind="input").inc(token_input)
        if token_output is not None:
            _MODEL_TOKENS.labels(**token_labels, kind="output").inc(token_output)
        if cost_estimate is not None:
            _MODEL_COST.labels(**token_labels).inc(float(cost_estimate))
        get_logger("model.telemetry").info(
            "model.completed",
            provider=provider,
            model=model,
            operation=operation,
            outcome=outcome,
            latency_ms=latency_ms,
            token_input=token_input,
            token_output=token_output,
            cost_recorded=cost_estimate is not None,
        )

    def parsing_failure(self, *, outcome: str) -> None:
        _PARSING_FAILURES.labels(outcome=outcome).inc()
        get_logger("documents.telemetry").warning("document.parse_failed", outcome=outcome)

    def evaluation_cases(self, *, passed_cases: int, total_cases: int) -> None:
        if passed_cases:
            _EVALUATION_CASES.labels(outcome="passed").inc(passed_cases)
        failed_cases = max(0, total_cases - passed_cases)
        if failed_cases:
            _EVALUATION_CASES.labels(outcome="failed").inc(failed_cases)
        get_logger("evaluation.telemetry").info(
            "evaluation.completed", passed_cases=passed_cases, total_cases=total_cases
        )

    def approval_decision(self, *, decision: str) -> None:
        _APPROVAL_DECISIONS.labels(decision=decision).inc()
        get_logger("approval.telemetry").info("approval.decided", decision=decision)

    def rag_refusal(self, *, reason: str) -> None:
        _RAG_REFUSALS.labels(reason=reason).inc()
        get_logger("retrieval.telemetry").info("rag.refused", reason=reason)


_TELEMETRY = Telemetry()


def get_telemetry() -> Telemetry:
    """Return the process-local telemetry façade."""

    return _TELEMETRY


def configure_observability(settings: AppSettings) -> None:
    """Configure optional OTLP trace export once for the running process."""

    global _TRACING_CONFIGURED
    if _TRACING_CONFIGURED or settings.otlp_endpoint is None:
        return
    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.release,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=f"{settings.otlp_endpoint}/v1/traces",
                timeout=settings.otlp_export_timeout_seconds,
            )
        )
    )
    trace.set_tracer_provider(provider)
    _TRACING_CONFIGURED = True


def metrics_payload() -> bytes:
    """Render the API-owned Prometheus registry without a tenant-specific view."""

    return generate_latest(_REGISTRY)


def inject_trace_headers() -> dict[str, str]:
    """Return only W3C trace headers for trusted Celery task metadata."""

    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return {key: value for key, value in carrier.items() if key in {"traceparent", "tracestate"}}


def instrument_celery_task(
    task_name: str,
) -> Callable[[Callable[TaskParameters, TaskResult]], Callable[TaskParameters, TaskResult]]:
    """Wrap a bound Celery task with safe logs and header-only trace extraction."""

    def decorate(
        function: Callable[TaskParameters, TaskResult],
    ) -> Callable[TaskParameters, TaskResult]:
        @wraps(function)
        def wrapped(*args: TaskParameters.args, **kwargs: TaskParameters.kwargs) -> TaskResult:
            task = args[0] if args else None
            request = getattr(task, "request", None)
            headers = getattr(request, "headers", None)
            carrier = headers if isinstance(headers, dict) else {}
            token = attach(propagate.extract(carrier))
            retries = getattr(request, "retries", 0)
            retry_count = retries if isinstance(retries, int) and retries >= 0 else 0
            logger = get_logger("workers.task")
            started = perf_counter()
            logger.info("worker.task_started", task_name=task_name, retry_count=retry_count)
            try:
                with get_telemetry().span(
                    "worker.task",
                    {"celery.task.name": task_name, "celery.task.retry_count": retry_count},
                ):
                    result = function(*args, **kwargs)
            except Exception:
                logger.warning(
                    "worker.task_failed",
                    task_name=task_name,
                    retry_count=retry_count,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
                raise
            else:
                logger.info(
                    "worker.task_completed",
                    task_name=task_name,
                    retry_count=retry_count,
                    outcome=str(result),
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
                return result
            finally:
                detach(token)

        return wrapped

    return decorate
