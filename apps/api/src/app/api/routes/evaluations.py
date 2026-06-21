"""Protected canonical deterministic evaluation dataset and run operations."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Header, Path, Query, Request, Response, status

from app.api.dependencies import CurrentPrincipalDependency, EvaluationServiceDependency
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.api.schemas.evaluations import (
    EvaluationDatasetData,
    EvaluationDatasetListData,
    EvaluationFailureCodeCountData,
    EvaluationMetricsData,
    EvaluationReportExportRequest,
    EvaluationResultData,
    EvaluationRunData,
    EvaluationRunDetailData,
    EvaluationRunListData,
    EvaluationRunStartRequest,
)
from app.services.common.pagination import Page, Pagination
from app.services.evaluation.reporting import EvaluationResultProjection, EvaluationRunProjection
from app.services.evaluation.service import CanonicalDatasetRecord

PREFIX = "/evaluations"
TAG = "Evaluations"
DESCRIPTION = "Protected canonical deterministic evaluation datasets and tenant run history."

router = APIRouter()

_EVALUATION_ERRORS = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Administrator access is required."},
    404: {"model": ErrorResponse, "description": "The evaluation resource was not found."},
    409: {"model": ErrorResponse, "description": "An evaluation run is already active."},
    503: {"model": ErrorResponse, "description": "Evaluation processing is unavailable."},
}


@router.get(
    "/datasets",
    response_model=SuccessResponse[EvaluationDatasetListData],
    responses=_EVALUATION_ERRORS,
    summary="List server-owned canonical evaluation datasets",
)
async def list_datasets(
    request: Request,
    principal: CurrentPrincipalDependency,
    evaluations: EvaluationServiceDependency,
) -> SuccessResponse[EvaluationDatasetListData]:
    records = await evaluations.list_canonical_datasets(principal)
    return SuccessResponse(
        data=EvaluationDatasetListData(items=tuple(_dataset_data(item) for item in records)),
        meta=_meta(request),
    )


@router.post(
    "/datasets/{dataset_key}/runs",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[EvaluationRunData],
    responses=_EVALUATION_ERRORS,
    summary="Queue one current-organization canonical evaluation run",
)
async def start_run(
    dataset_key: Annotated[str, Path(pattern=r"^[a-z][a-z0-9-]{2,63}$")],
    _payload: EvaluationRunStartRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    evaluations: EvaluationServiceDependency,
) -> SuccessResponse[EvaluationRunData]:
    run = await evaluations.start(principal, dataset_key=dataset_key)
    return SuccessResponse(data=_run_data(run), meta=_meta(request))


@router.get(
    "/runs",
    response_model=SuccessResponse[EvaluationRunListData],
    responses=_EVALUATION_ERRORS,
    summary="List current-organization evaluation runs",
)
async def list_runs(
    request: Request,
    principal: CurrentPrincipalDependency,
    evaluations: EvaluationServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    run_status: Annotated[
        str | None, Query(alias="status", pattern="^(queued|running|completed|failed)$")
    ] = None,
) -> SuccessResponse[EvaluationRunListData]:
    page = await evaluations.list_runs(
        principal, pagination=Pagination(limit=limit, offset=offset), status=run_status
    )
    return SuccessResponse(data=_run_list_data(page), meta=_meta(request))


@router.get(
    "/runs/{evaluation_run_id}",
    response_model=SuccessResponse[EvaluationRunDetailData],
    responses=_EVALUATION_ERRORS,
    summary="Inspect one current-organization evaluation run and safe result metrics",
)
async def get_run(
    evaluation_run_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    evaluations: EvaluationServiceDependency,
) -> SuccessResponse[EvaluationRunDetailData]:
    record = await evaluations.get_run(principal, evaluation_run_id)
    return SuccessResponse(data=_run_detail_data(record), meta=_meta(request))


@router.get(
    "/runs/{evaluation_run_id}/results/{evaluation_result_id}",
    response_model=SuccessResponse[EvaluationResultData],
    responses=_EVALUATION_ERRORS,
    summary="Inspect one safe current-organization evaluation result",
)
async def get_result(
    evaluation_run_id: UUID,
    evaluation_result_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    evaluations: EvaluationServiceDependency,
) -> SuccessResponse[EvaluationResultData]:
    result = await evaluations.get_result(principal, evaluation_run_id, evaluation_result_id)
    return SuccessResponse(data=_result_data(result), meta=_meta(request))


@router.post(
    "/runs/{evaluation_run_id}/report",
    response_class=Response,
    responses={
        **_EVALUATION_ERRORS,
        200: {
            "content": {"text/markdown": {"schema": {"type": "string"}}},
            "description": "A bounded server-generated Markdown evaluation report.",
        },
    },
    summary="Export one safe current-organization Markdown evaluation report",
)
async def export_report(
    evaluation_run_id: UUID,
    _payload: EvaluationReportExportRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    evaluations: EvaluationServiceDependency,
    accept_language: Annotated[str | None, Header()] = None,
) -> Response:
    report = await evaluations.export_report(
        principal,
        evaluation_run_id,
        locale=accept_language or "nb",
    )
    _ = request
    return Response(
        content=report,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="evaluation-report.md"'},
    )


def _dataset_data(record: CanonicalDatasetRecord) -> EvaluationDatasetData:
    dataset = record.dataset
    return EvaluationDatasetData(
        dataset_id=dataset.id,
        dataset_key=dataset.dataset_key,
        version=dataset.dataset_version,
        content_hash=dataset.content_hash,
        description=dataset.description,
    )


def _run_data(run: EvaluationRunProjection) -> EvaluationRunData:
    return EvaluationRunData(
        evaluation_run_id=run.evaluation_run_id,
        dataset_key=run.dataset_key,
        dataset_version=run.dataset_version,
        dataset_content_hash=run.dataset_content_hash,
        status=cast(Literal["queued", "running", "completed", "failed"], run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        pass_fail=cast(Literal["pending", "pass", "fail"], run.pass_fail),
        metrics=_metrics_data(run),
    )


def _metrics_data(run: EvaluationRunProjection) -> EvaluationMetricsData:
    metrics = run.metrics
    return EvaluationMetricsData(
        case_total=metrics.case_total,
        passed_case_total=metrics.passed_case_total,
        failed_case_total=metrics.failed_case_total,
        retrieval_mean=_float_or_none(metrics.retrieval_mean),
        citation_mean=_float_or_none(metrics.citation_mean),
        structural_faithfulness_mean=_float_or_none(metrics.structural_faithfulness_mean),
        refusal_mean=_float_or_none(metrics.refusal_mean),
        risk_mean=_float_or_none(metrics.risk_mean),
        routing_mean=_float_or_none(metrics.routing_mean),
        average_latency_ms=metrics.average_latency_ms,
        latency_sample_count=metrics.latency_sample_count,
        total_cost_estimate=_float_or_none(metrics.total_cost_estimate),
        cost_sample_count=metrics.cost_sample_count,
        failure_code_counts=tuple(
            EvaluationFailureCodeCountData(code=item.code, count=item.count)
            for item in metrics.failure_code_counts
        ),
        run_failure_code=metrics.run_failure_code,
    )


def _result_data(result: EvaluationResultProjection) -> EvaluationResultData:
    return EvaluationResultData(
        evaluation_result_id=result.evaluation_result_id,
        case_key=result.case_key,
        retrieval_score=_float_or_none(result.retrieval_score),
        citation_score=_float_or_none(result.citation_score),
        structural_faithfulness_score=_float_or_none(result.structural_faithfulness_score),
        refusal_score=_float_or_none(result.refusal_score),
        risk_score=_float_or_none(result.risk_score),
        routing_score=_float_or_none(result.routing_score),
        latency_ms=result.latency_ms,
        cost_estimate=_float_or_none(result.cost_estimate),
        passed=result.passed,
        failure_codes=result.failure_codes,
    )


def _run_detail_data(record: EvaluationRunProjection) -> EvaluationRunDetailData:
    return EvaluationRunDetailData(
        run=_run_data(record), results=tuple(_result_data(item) for item in record.results)
    )


def _float_or_none(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _run_list_data(page: Page[EvaluationRunProjection]) -> EvaluationRunListData:
    return EvaluationRunListData(
        items=tuple(_run_data(item) for item in page.items),
        limit=page.limit,
        offset=page.offset,
        total=page.total,
        has_more=page.has_more,
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
