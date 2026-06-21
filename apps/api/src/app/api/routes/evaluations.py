"""Protected canonical deterministic evaluation dataset and run operations."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Path, Query, Request, status

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
    EvaluationResultData,
    EvaluationRunData,
    EvaluationRunDetailData,
    EvaluationRunListData,
    EvaluationRunStartRequest,
)
from app.db.models.evaluation import EvalResult, EvalRun
from app.services.common.pagination import Page, Pagination
from app.services.evaluation.service import CanonicalDatasetRecord, EvaluationRunRecord

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


def _dataset_data(record: CanonicalDatasetRecord) -> EvaluationDatasetData:
    dataset = record.dataset
    return EvaluationDatasetData(
        dataset_id=dataset.id,
        dataset_key=dataset.dataset_key,
        version=dataset.dataset_version,
        content_hash=dataset.content_hash,
        description=dataset.description,
    )


def _run_data(run: EvalRun) -> EvaluationRunData:
    return EvaluationRunData(
        evaluation_run_id=run.id,
        dataset_id=run.eval_dataset_id,
        dataset_version=run.dataset_version,
        dataset_content_hash=run.dataset_content_hash,
        status=cast(Literal["queued", "running", "completed", "failed"], run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        pass_fail=cast(Literal["pending", "pass", "fail"], run.pass_fail),
        summary=dict(run.summary_metrics),
    )


def _result_data(result: EvalResult, *, case_key: str) -> EvaluationResultData:
    raw_codes = result.failure_reasons.get("codes")
    codes = (
        tuple(code for code in raw_codes if isinstance(code, str))
        if isinstance(raw_codes, list)
        else ()
    )
    return EvaluationResultData(
        evaluation_result_id=result.id,
        evaluation_case_id=result.eval_case_id,
        case_key=case_key,
        retrieval_score=float(result.retrieval_score)
        if result.retrieval_score is not None
        else None,
        citation_score=(
            float(result.citation_score) if result.citation_score is not None else None
        ),
        structural_faithfulness_score=(
            float(result.faithfulness_score) if result.faithfulness_score is not None else None
        ),
        refusal_score=float(result.refusal_score) if result.refusal_score is not None else None,
        risk_score=float(result.risk_score) if result.risk_score is not None else None,
        routing_score=float(result.routing_score) if result.routing_score is not None else None,
        passed=result.passed,
        failure_codes=codes,
    )


def _run_detail_data(record: EvaluationRunRecord) -> EvaluationRunDetailData:
    return EvaluationRunDetailData(
        run=_run_data(record.run),
        results=tuple(
            _result_data(item, case_key=record.result_case_keys[item.id]) for item in record.results
        ),
    )


def _run_list_data(page: Page[EvalRun]) -> EvaluationRunListData:
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
