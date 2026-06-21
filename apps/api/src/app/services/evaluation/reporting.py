"""Strict, content-free projections and Markdown reports for evaluation history."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from app.db.models.evaluation import EvalResult, EvalRun

type CaseFailureCode = Literal[
    "retrieval_mismatch",
    "citation_mismatch",
    "criterion_mismatch",
    "refusal_mismatch",
    "risk_mismatch",
    "routing_mismatch",
]
type RunFailureCode = Literal[
    "dispatch_unavailable",
    "dataset_not_available",
    "dataset_identity_mismatch",
    "dataset_cases_unavailable",
    "deterministic_runner_failed",
    "worker_runtime_unavailable",
]

CASE_FAILURE_CODES: tuple[CaseFailureCode, ...] = (
    "retrieval_mismatch",
    "citation_mismatch",
    "criterion_mismatch",
    "refusal_mismatch",
    "risk_mismatch",
    "routing_mismatch",
)
RUN_FAILURE_CODES: tuple[RunFailureCode, ...] = (
    "dispatch_unavailable",
    "dataset_not_available",
    "dataset_identity_mismatch",
    "dataset_cases_unavailable",
    "deterministic_runner_failed",
    "worker_runtime_unavailable",
)

_SCORE_QUANTUM = Decimal("0.0001")
_COST_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class EvaluationResultProjection:
    """One result with only dashboard-safe identifiers and measurements."""

    evaluation_result_id: UUID
    case_key: str
    retrieval_score: Decimal | None
    citation_score: Decimal | None
    structural_faithfulness_score: Decimal | None
    refusal_score: Decimal | None
    risk_score: Decimal | None
    routing_score: Decimal | None
    latency_ms: int | None
    cost_estimate: Decimal | None
    passed: bool
    failure_codes: tuple[CaseFailureCode, ...]


@dataclass(frozen=True)
class EvaluationFailureCodeCount:
    code: CaseFailureCode
    count: int


@dataclass(frozen=True)
class EvaluationMetricsProjection:
    """Aggregate values whose nullability distinguishes unavailable from zero."""

    case_total: int
    passed_case_total: int
    failed_case_total: int
    retrieval_mean: Decimal | None
    citation_mean: Decimal | None
    structural_faithfulness_mean: Decimal | None
    refusal_mean: Decimal | None
    risk_mean: Decimal | None
    routing_mean: Decimal | None
    average_latency_ms: int | None
    latency_sample_count: int
    total_cost_estimate: Decimal | None
    cost_sample_count: int
    failure_code_counts: tuple[EvaluationFailureCodeCount, ...]
    run_failure_code: RunFailureCode | None


@dataclass(frozen=True)
class EvaluationRunProjection:
    """The exact safe model shared by JSON operations and report rendering."""

    evaluation_run_id: UUID
    dataset_key: str
    dataset_version: str
    dataset_content_hash: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    pass_fail: str
    metrics: EvaluationMetricsProjection
    results: tuple[EvaluationResultProjection, ...]


def project_result(result: EvalResult, *, case_key: str) -> EvaluationResultProjection:
    """Project one persisted result, suppressing malformed or unclosed values."""

    return EvaluationResultProjection(
        evaluation_result_id=result.id,
        case_key=case_key,
        retrieval_score=_safe_score(result.retrieval_score),
        citation_score=_safe_score(result.citation_score),
        structural_faithfulness_score=_safe_score(result.faithfulness_score),
        refusal_score=_safe_score(result.refusal_score),
        risk_score=_safe_score(result.risk_score),
        routing_score=_safe_score(result.routing_score),
        latency_ms=_safe_latency(result.latency_ms),
        cost_estimate=_safe_cost(result.cost_estimate),
        passed=bool(result.passed),
        failure_codes=_closed_failure_codes(result.failure_reasons),
    )


def project_run(
    run: EvalRun,
    *,
    dataset_key: str,
    results: Iterable[EvaluationResultProjection],
) -> EvaluationRunProjection:
    """Return a deterministic run projection without exposing ``summary_metrics``."""

    ordered_results = tuple(
        sorted(results, key=lambda item: (item.case_key, str(item.evaluation_result_id)))
    )
    metrics = _metrics_for(run, ordered_results)
    return EvaluationRunProjection(
        evaluation_run_id=run.id,
        dataset_key=dataset_key,
        dataset_version=run.dataset_version,
        dataset_content_hash=run.dataset_content_hash,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        pass_fail=run.pass_fail,
        metrics=metrics,
        results=ordered_results,
    )


def render_markdown_report(projection: EvaluationRunProjection, *, locale: str) -> str:
    """Render one bounded server-owned report from the same safe projection as the API."""

    labels = _report_labels(locale)
    metrics = projection.metrics
    lines = [
        f"# {labels['title']}",
        "",
        f"- {labels['dataset_version']}: `{_markdown(projection.dataset_version)}`",
        f"- {labels['dataset_hash']}: `{_markdown(projection.dataset_content_hash)}`",
        f"- {labels['status']}: `{_markdown(projection.status)}`",
        f"- {labels['pass_fail']}: `{_markdown(projection.pass_fail)}`",
        f"- {labels['started_at']}: `{_timestamp(projection.started_at)}`",
        f"- {labels['finished_at']}: `{_timestamp(projection.finished_at)}`",
        "",
        f"## {labels['metrics']}",
        "",
        f"- {labels['case_total']}: {_number(metrics.case_total)}",
        f"- {labels['passed_case_total']}: {_number(metrics.passed_case_total)}",
        f"- {labels['failed_case_total']}: {_number(metrics.failed_case_total)}",
        f"- {labels['retrieval']}: {_score(metrics.retrieval_mean, labels)}",
        f"- {labels['citation']}: {_score(metrics.citation_mean, labels)}",
        (
            f"- {labels['structural_faithfulness']}: "
            f"{_score(metrics.structural_faithfulness_mean, labels)}"
        ),
        f"- {labels['refusal']}: {_score(metrics.refusal_mean, labels)}",
        f"- {labels['risk']}: {_score(metrics.risk_mean, labels)}",
        f"- {labels['routing']}: {_score(metrics.routing_mean, labels)}",
        f"- {labels['latency']}: {_latency(metrics, labels)}",
        f"- {labels['cost']}: {_cost(metrics, labels)}",
    ]
    if metrics.run_failure_code is not None:
        lines.append(f"- {labels['run_failure_code']}: `{_markdown(metrics.run_failure_code)}`")
    lines.extend(("", f"## {labels['failure_codes']}", ""))
    if metrics.failure_code_counts:
        lines.extend(
            f"- `{_markdown(item.code)}`: {_number(item.count)}"
            for item in metrics.failure_code_counts
        )
    else:
        lines.append(labels["none"])

    failed_results = tuple(item for item in projection.results if not item.passed)
    lines.extend(("", f"## {labels['failed_cases']}", ""))
    if not failed_results:
        lines.append(labels["none"])
    else:
        lines.extend(
            (
                "| "
                + " | ".join(
                    (
                        labels["case_key"],
                        labels["retrieval"],
                        labels["citation"],
                        labels["structural_faithfulness"],
                        labels["refusal"],
                        labels["risk"],
                        labels["routing"],
                        labels["failure_codes"],
                    )
                )
                + " |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            )
        )
        for item in failed_results:
            lines.append(
                "| "
                + " | ".join(
                    (
                        _markdown(item.case_key),
                        _score(item.retrieval_score, labels),
                        _score(item.citation_score, labels),
                        _score(item.structural_faithfulness_score, labels),
                        _score(item.refusal_score, labels),
                        _score(item.risk_score, labels),
                        _score(item.routing_score, labels),
                        ", ".join(f"`{_markdown(code)}`" for code in item.failure_codes)
                        or labels["none"],
                    )
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def report_locale(value: str | None) -> Literal["nb", "en"]:
    """Map an HTTP language header to the two fixed report label sets."""

    if value is not None:
        primary = value.split(",", maxsplit=1)[0].strip().lower()
        if primary == "en" or primary.startswith("en-"):
            return "en"
    return "nb"


def _metrics_for(
    run: EvalRun, results: tuple[EvaluationResultProjection, ...]
) -> EvaluationMetricsProjection:
    failure_counts: Counter[CaseFailureCode] = Counter(
        code for result in results for code in result.failure_codes
    )
    latency_values = tuple(
        Decimal(item.latency_ms) for item in results if item.latency_ms is not None
    )
    cost_values = tuple(item.cost_estimate for item in results if item.cost_estimate is not None)
    return EvaluationMetricsProjection(
        case_total=len(results),
        passed_case_total=sum(item.passed for item in results),
        failed_case_total=sum(not item.passed for item in results),
        retrieval_mean=_mean(item.retrieval_score for item in results),
        citation_mean=_mean(item.citation_score for item in results),
        structural_faithfulness_mean=_mean(item.structural_faithfulness_score for item in results),
        refusal_mean=_mean(item.refusal_score for item in results),
        risk_mean=_mean(item.risk_score for item in results),
        routing_mean=_mean(item.routing_score for item in results),
        average_latency_ms=(
            int(
                (sum(latency_values, Decimal(0)) / len(latency_values)).quantize(
                    Decimal("1"), ROUND_HALF_UP
                )
            )
            if latency_values
            else None
        ),
        latency_sample_count=len(latency_values),
        total_cost_estimate=sum(cost_values, Decimal(0)).quantize(_COST_QUANTUM, ROUND_HALF_UP)
        if cost_values
        else None,
        cost_sample_count=len(cost_values),
        failure_code_counts=tuple(
            EvaluationFailureCodeCount(code=code, count=failure_counts[code])
            for code in CASE_FAILURE_CODES
            if failure_counts[code]
        ),
        run_failure_code=_closed_run_failure_code(run.summary_metrics),
    )


def _mean(values: Iterable[Decimal | None]) -> Decimal | None:
    present = tuple(value for value in values if value is not None)
    if not present:
        return None
    return (sum(present, Decimal(0)) / len(present)).quantize(_SCORE_QUANTUM, ROUND_HALF_UP)


def _safe_score(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal = Decimal(value)
    except (ArithmeticError, TypeError, ValueError):
        return None
    return decimal if Decimal("0") <= decimal <= Decimal("1") else None


def _safe_latency(value: int | None) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _safe_cost(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal = Decimal(value)
    except (ArithmeticError, TypeError, ValueError):
        return None
    return decimal if decimal >= 0 else None


def _closed_failure_codes(value: dict[str, object]) -> tuple[CaseFailureCode, ...]:
    raw_codes = value.get("codes")
    if not isinstance(raw_codes, list):
        return ()
    known: set[CaseFailureCode] = {
        code for code in raw_codes if isinstance(code, str) and code in CASE_FAILURE_CODES
    }
    return tuple(code for code in CASE_FAILURE_CODES if code in known)


def _closed_run_failure_code(value: dict[str, object]) -> RunFailureCode | None:
    candidate = value.get("failure_code")
    if isinstance(candidate, str) and candidate in RUN_FAILURE_CODES:
        return candidate
    return None


def _report_labels(locale: str) -> dict[str, str]:
    if report_locale(locale) == "en":
        return {
            "title": "Evaluation report",
            "dataset_version": "Dataset version",
            "dataset_hash": "Dataset hash",
            "status": "Status",
            "pass_fail": "Pass/fail",
            "started_at": "Started",
            "finished_at": "Finished",
            "metrics": "Metrics",
            "case_total": "Cases",
            "passed_case_total": "Passed cases",
            "failed_case_total": "Failed cases",
            "retrieval": "Retrieval score",
            "citation": "Citation score",
            "structural_faithfulness": "Structural faithfulness score",
            "refusal": "Refusal behavior score",
            "risk": "Risk score",
            "routing": "Routing score",
            "latency": "Recorded average latency",
            "cost": "Recorded estimated cost",
            "run_failure_code": "Run failure code",
            "failure_codes": "Regression failure codes",
            "failed_cases": "Failed cases",
            "case_key": "Case key",
            "none": "Not recorded",
        }
    return {
        "title": "Evalueringsrapport",
        "dataset_version": "Datasettversjon",
        "dataset_hash": "Datasett-hash",
        "status": "Status",
        "pass_fail": "Bestått/ikke bestått",
        "started_at": "Startet",
        "finished_at": "Fullført",
        "metrics": "Målinger",
        "case_total": "Tilfeller",
        "passed_case_total": "Beståtte tilfeller",
        "failed_case_total": "Mislykkede tilfeller",
        "retrieval": "Gjenfinningsscore",
        "citation": "Siteringsscore",
        "structural_faithfulness": "Strukturell trofasthetsscore",
        "refusal": "Avvisningsatferdsscore",
        "risk": "Risikoscore",
        "routing": "Rutescore",
        "latency": "Registrert gjennomsnittlig forsinkelse",
        "cost": "Registrert estimert kostnad",
        "run_failure_code": "Feilkode for kjøring",
        "failure_codes": "Regresjonsfeilkoder",
        "failed_cases": "Mislykkede tilfeller",
        "case_key": "Tilfellenøkkel",
        "none": "Ikke registrert",
    }


def _score(value: Decimal | None, labels: dict[str, str]) -> str:
    return f"{value:.4f}" if value is not None else labels["none"]


def _latency(metrics: EvaluationMetricsProjection, labels: dict[str, str]) -> str:
    if metrics.average_latency_ms is None:
        return labels["none"]
    samples = f"{_number(metrics.latency_sample_count)}/{_number(metrics.case_total)}"
    return f"{_number(metrics.average_latency_ms)} ms ({samples})"


def _cost(metrics: EvaluationMetricsProjection, labels: dict[str, str]) -> str:
    if metrics.total_cost_estimate is None:
        return labels["none"]
    samples = f"{_number(metrics.cost_sample_count)}/{_number(metrics.case_total)}"
    return f"{metrics.total_cost_estimate:.6f} ({samples})"


def _number(value: int) -> str:
    return str(value)


def _timestamp(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def _markdown(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
