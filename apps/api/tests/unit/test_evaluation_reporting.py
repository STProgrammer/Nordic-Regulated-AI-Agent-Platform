"""Focused safe-projection coverage for the Phase 26 evaluation surface."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.db.models.evaluation import EvalResult, EvalRun
from app.services.evaluation.reporting import (
    project_result,
    project_run,
    render_markdown_report,
)


def _run(*, summary_metrics: dict[str, object] | None = None) -> EvalRun:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    return EvalRun(
        id=uuid4(),
        organization_id=uuid4(),
        eval_dataset_id=uuid4(),
        dataset_version="v1",
        dataset_content_hash="a" * 64,
        run_name="nordic-regulated-core-v1-v1",
        status="completed",
        started_at=now,
        finished_at=now,
        summary_metrics=summary_metrics or {},
        pass_fail="fail",
        inserted_at=now,
    )


def _result(
    *,
    retrieval: str | None = "1",
    latency_ms: int | None = None,
    cost_estimate: str | None = None,
    passed: bool,
    codes: list[object],
) -> EvalResult:
    return EvalResult(
        id=uuid4(),
        eval_run_id=uuid4(),
        eval_case_id=uuid4(),
        retrieval_score=Decimal(retrieval) if retrieval is not None else None,
        citation_score=Decimal("0.5"),
        faithfulness_score=Decimal("0.33335"),
        refusal_score=Decimal("1"),
        risk_score=Decimal("0"),
        routing_score=Decimal("1"),
        latency_ms=latency_ms,
        cost_estimate=Decimal(cost_estimate) if cost_estimate is not None else None,
        passed=passed,
        failure_reasons={"codes": codes, "query": "phase26-hidden-sentinel"},
        inserted_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


def test_projection_aggregates_allowlisted_metrics_without_false_zeroes() -> None:
    run = _run(summary_metrics={"failure_code": "dispatch_unavailable", "query": "hidden"})
    failed = project_result(
        _result(
            retrieval="0.33335",
            latency_ms=5,
            cost_estimate="0.100001",
            passed=False,
            codes=["retrieval_mismatch", "unexpected_raw_reason", "retrieval_mismatch"],
        ),
        case_key="case_b",
    )
    passed = project_result(
        _result(
            retrieval="1",
            latency_ms=None,
            cost_estimate=None,
            passed=True,
            codes=[],
        ),
        case_key="case_a",
    )

    projection = project_run(run, dataset_key="nordic-regulated-core-v1", results=(failed, passed))

    assert tuple(item.case_key for item in projection.results) == ("case_a", "case_b")
    assert projection.metrics.case_total == 2
    assert projection.metrics.passed_case_total == 1
    assert projection.metrics.failed_case_total == 1
    assert projection.metrics.retrieval_mean == Decimal("0.6667")
    assert projection.metrics.structural_faithfulness_mean == Decimal("0.3334")
    assert projection.metrics.average_latency_ms == 5
    assert projection.metrics.latency_sample_count == 1
    assert projection.metrics.total_cost_estimate == Decimal("0.100001")
    assert projection.metrics.cost_sample_count == 1
    assert projection.metrics.run_failure_code == "dispatch_unavailable"
    assert projection.metrics.failure_code_counts[0].code == "retrieval_mismatch"
    assert projection.metrics.failure_code_counts[0].count == 1
    assert failed.failure_codes == ("retrieval_mismatch",)


def test_projection_keeps_recorded_zero_distinct_from_missing_measurements() -> None:
    run = _run()
    zero = project_result(
        _result(latency_ms=0, cost_estimate="0", passed=True, codes=[]), case_key="case_zero"
    )
    projection = project_run(run, dataset_key="nordic-regulated-core-v1", results=(zero,))
    empty = project_run(run, dataset_key="nordic-regulated-core-v1", results=())

    assert projection.metrics.average_latency_ms == 0
    assert projection.metrics.total_cost_estimate == Decimal("0.000000")
    assert projection.metrics.latency_sample_count == 1
    assert projection.metrics.cost_sample_count == 1
    assert empty.metrics.average_latency_ms is None
    assert empty.metrics.total_cost_estimate is None
    assert empty.metrics.latency_sample_count == 0
    assert empty.metrics.cost_sample_count == 0
    assert empty.metrics.retrieval_mean is None


def test_markdown_report_is_deterministic_localized_and_content_free() -> None:
    run = _run(summary_metrics={"failure_code": "not_an_allowed_code", "query": "hidden"})
    failed = project_result(
        _result(
            latency_ms=None,
            cost_estimate=None,
            passed=False,
            codes=["citation_mismatch", "phase26-hidden-sentinel"],
        ),
        case_key="case|failed",
    )
    passed = project_result(
        _result(passed=True, codes=[]),
        case_key="case_passed",
    )
    projection = project_run(
        run,
        dataset_key="nordic-regulated-core-v1",
        results=(passed, failed),
    )

    bokmal = render_markdown_report(projection, locale="nb-NO,nb;q=0.9")
    english = render_markdown_report(projection, locale="en")

    assert bokmal.startswith("# Evalueringsrapport\n")
    assert "Ikke registrert" in bokmal
    assert "case\\|failed" in bokmal
    assert "citation_mismatch" in bokmal
    assert "case_passed" not in bokmal
    assert "phase26-hidden-sentinel" not in bokmal
    assert "hidden" not in bokmal
    assert "not_an_allowed_code" not in bokmal
    assert english.startswith("# Evaluation report\n")
