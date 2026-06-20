"""Protected Case Management HTTP operations."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies import (
    CaseServiceDependency,
    CurrentPrincipalDependency,
    get_evidence_workflow_service,
    get_intake_workflow_service,
)
from app.api.schemas.cases import (
    CaseAssigneeListData,
    CaseAssigneeOptionData,
    CaseCreateRequest,
    CaseData,
    CaseDomain,
    CaseLanguage,
    CaseListData,
    CasePriority,
    CaseRiskLevel,
    CaseStatus,
    CaseSummaryData,
    CaseUpdateRequest,
)
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.api.schemas.workflows import WorkflowRunData, WorkflowStartRequest
from app.db.models.case import Case
from app.db.repositories.case import CaseFilters, Unset
from app.services.cases.service import CaseCreate, CasePatch
from app.services.common.pagination import Pagination
from app.services.common.querying import SortDirection, SortSpec
from app.services.workflows.evidence import EvidenceWorkflowService
from app.services.workflows.intake import IntakeWorkflowService

PREFIX = "/cases"
TAG = "Cases"
DESCRIPTION = "Protected organization-scoped case submission, lifecycle, and archive operations."

router = APIRouter()

_CASE_ERROR_RESPONSES = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "The current role is not allowed."},
    404: {"model": ErrorResponse, "description": "The case or referenced user was not found."},
    409: {"model": ErrorResponse, "description": "The case conflicts with existing data."},
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[CaseData],
    responses=_CASE_ERROR_RESPONSES,
    summary="Submit a case in the current organization",
)
async def create_case(
    payload: CaseCreateRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    cases: CaseServiceDependency,
) -> SuccessResponse[CaseData]:
    """Submit trusted user input without accepting caller-owned tenant or status fields."""

    case = await cases.submit(
        principal,
        CaseCreate(
            title=payload.title,
            description=payload.description,
            language=payload.language.value,
            domain=payload.domain.value,
            priority=payload.priority.value,
            due_date=payload.due_date,
            external_reference=payload.external_reference,
        ),
    )
    return SuccessResponse(data=_case_data(case), meta=_meta(request))


@router.get(
    "/assignees",
    response_model=SuccessResponse[CaseAssigneeListData],
    responses=_CASE_ERROR_RESPONSES,
    summary="List minimal assignee choices for the current Case Inbox",
)
async def list_case_assignees(
    request: Request,
    principal: CurrentPrincipalDependency,
    cases: CaseServiceDependency,
) -> SuccessResponse[CaseAssigneeListData]:
    """Return no more identity data than the Case assignee filter requires."""

    options = await cases.list_assignee_options(principal)
    return SuccessResponse(
        data=CaseAssigneeListData(
            items=tuple(
                CaseAssigneeOptionData(user_id=user_id, display_name=display_name)
                for user_id, display_name in options
            )
        ),
        meta=_meta(request),
    )


@router.get(
    "",
    response_model=SuccessResponse[CaseListData],
    responses=_CASE_ERROR_RESPONSES,
    summary="List active cases in the current organization",
)
async def list_cases(
    request: Request,
    principal: CurrentPrincipalDependency,
    cases: CaseServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[CaseStatus | None, Query(alias="status")] = None,
    risk_level: CaseRiskLevel | None = None,
    assigned_user_id: UUID | None = None,
    domain: CaseDomain | None = None,
    priority: CasePriority | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    sort: Literal[
        "inserted_at", "updated_at", "case_number", "title", "due_date", "priority", "status"
    ] = "inserted_at",
    direction: SortDirection = SortDirection.DESC,
) -> SuccessResponse[CaseListData]:
    """Return an allowlisted, bounded page suitable for the future Case Inbox."""

    page = await cases.list(
        principal,
        pagination=Pagination(limit=limit, offset=offset),
        filters=CaseFilters(
            status=status_filter.value if status_filter is not None else None,
            risk_level=risk_level.value if risk_level is not None else None,
            assigned_user_id=assigned_user_id,
            domain=domain.value if domain is not None else None,
            priority=priority.value if priority is not None else None,
            search_text=q.strip() if q is not None else None,
        ),
        sort=SortSpec(key=sort, direction=direction),
    )
    return SuccessResponse(
        data=CaseListData(
            items=tuple(_case_summary(case) for case in page.items),
            limit=page.limit,
            offset=page.offset,
            total=page.total,
            has_more=page.has_more,
        ),
        meta=_meta(request),
    )


@router.get(
    "/{case_id}",
    response_model=SuccessResponse[CaseData],
    responses=_CASE_ERROR_RESPONSES,
    summary="Get one active case in the current organization",
)
async def get_case(
    case_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    cases: CaseServiceDependency,
) -> SuccessResponse[CaseData]:
    """Load one active tenant case through the authorized domain service."""

    case = await cases.get_required(principal, case_id)
    return SuccessResponse(data=_case_data(case), meta=_meta(request))


@router.patch(
    "/{case_id}",
    response_model=SuccessResponse[CaseData],
    responses=_CASE_ERROR_RESPONSES,
    summary="Update case metadata, assignment, or lifecycle status",
)
async def update_case(
    case_id: UUID,
    payload: CaseUpdateRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    cases: CaseServiceDependency,
) -> SuccessResponse[CaseData]:
    """Keep request parsing thin while the service applies lifecycle and role policy."""

    fields = payload.model_fields_set
    case = await cases.patch(
        principal,
        case_id,
        CasePatch(
            title=(
                payload.title if "title" in fields and payload.title is not None else Unset.VALUE
            ),
            description=(
                payload.description
                if "description" in fields and payload.description is not None
                else Unset.VALUE
            ),
            language=payload.language.value
            if "language" in fields and payload.language
            else Unset.VALUE,
            domain=payload.domain.value if "domain" in fields and payload.domain else Unset.VALUE,
            priority=payload.priority.value
            if "priority" in fields and payload.priority
            else Unset.VALUE,
            status=payload.status.value if "status" in fields and payload.status else Unset.VALUE,
            assigned_user_id=(
                payload.assigned_user_id if "assigned_user_id" in fields else Unset.VALUE
            ),
            due_date=payload.due_date if "due_date" in fields else Unset.VALUE,
            external_reference=(
                payload.external_reference if "external_reference" in fields else Unset.VALUE
            ),
        ),
    )
    return SuccessResponse(data=_case_data(case), meta=_meta(request))


@router.post(
    "/{case_id}/archive",
    response_model=SuccessResponse[CaseData],
    responses=_CASE_ERROR_RESPONSES,
    summary="Archive one active case",
)
async def archive_case(
    case_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    cases: CaseServiceDependency,
) -> SuccessResponse[CaseData]:
    """Archive is intentionally a dedicated operation rather than a patch status value."""

    case = await cases.archive(principal, case_id)
    return SuccessResponse(data=_case_data(case), meta=_meta(request))


@router.post(
    "/{case_id}/workflows/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SuccessResponse[WorkflowRunData],
    responses={
        **_CASE_ERROR_RESPONSES,
        503: {"model": ErrorResponse, "description": "Workflow processing is unavailable."},
    },
    summary="Queue a closed supported workflow for one current-tenant case",
)
async def start_case_workflow(
    case_id: UUID,
    payload: WorkflowStartRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    workflows: Annotated[IntakeWorkflowService, Depends(get_intake_workflow_service)],
    evidence_workflows: Annotated[EvidenceWorkflowService, Depends(get_evidence_workflow_service)],
) -> SuccessResponse[WorkflowRunData]:
    """Accept only fixed selectors; all model, state, and queue inputs stay server-owned."""

    run = (
        await workflows.start(principal, case_id)
        if payload.workflow == "intake"
        else await evidence_workflows.start(principal, case_id)
    )
    return SuccessResponse(data=_workflow_run_data(run), meta=_meta(request))


def _case_data(case: Case) -> CaseData:
    return CaseData(
        case_id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        language=CaseLanguage(case.language),
        domain=CaseDomain(case.domain),
        case_type=case.case_type,
        priority=CasePriority(case.priority),
        status=CaseStatus(case.status),
        risk_level=CaseRiskLevel(case.risk_level) if case.risk_level is not None else None,
        assigned_user_id=case.assigned_user_id,
        submitted_by_user_id=case.submitted_by_user_id,
        due_date=case.due_date,
        external_reference=case.external_reference,
        inserted_at=case.inserted_at,
        updated_at=case.updated_at,
        archived_at=case.archived_at,
    )


def _case_summary(case: Case) -> CaseSummaryData:
    return CaseSummaryData(
        case_id=case.id,
        case_number=case.case_number,
        title=case.title,
        language=CaseLanguage(case.language),
        domain=CaseDomain(case.domain),
        priority=CasePriority(case.priority),
        status=CaseStatus(case.status),
        risk_level=CaseRiskLevel(case.risk_level) if case.risk_level is not None else None,
        assigned_user_id=case.assigned_user_id,
        submitted_by_user_id=case.submitted_by_user_id,
        due_date=case.due_date,
        inserted_at=case.inserted_at,
        updated_at=case.updated_at,
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)


def _workflow_run_data(run: object) -> WorkflowRunData:
    """Keep a queued start response intentionally sparse and safe."""

    from app.api.routes.workflows import workflow_run_data

    return workflow_run_data(run)
