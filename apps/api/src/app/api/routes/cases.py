"""Protected Case Management HTTP operations."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from agent_orchestrator.graphs.drafting_types import DraftKind, OutputLanguage
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies import (
    AuditServiceDependency,
    CaseServiceDependency,
    CurrentPrincipalDependency,
    RouteRateLimiterDependency,
    SettingsDependency,
    get_drafting_workflow_service,
    get_evidence_workflow_service,
    get_extraction_workflow_service,
    get_intake_workflow_service,
    get_risk_workflow_service,
)
from app.api.route_rate_limit import enforce_route_rate_limit
from app.api.routes.audit import audit_page_data
from app.api.schemas.audit import AuditEventListData
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
from app.api.schemas.workflows import (
    DraftCitationData,
    DraftData,
    ExtractedFieldData,
    ExtractedFieldEditRequest,
    ExtractedFieldListData,
    RiskAssessmentData,
    WorkflowRunData,
    WorkflowStartRequest,
)
from app.core.rate_limit import RouteRateLimitPolicy
from app.db.models.case import Case
from app.db.repositories.case import CaseFilters, Unset
from app.services.cases.service import CasePatch, CaseSubmission
from app.services.common.pagination import Pagination
from app.services.common.querying import SortDirection, SortSpec
from app.services.workflows.drafting import DraftingWorkflowService
from app.services.workflows.evidence import EvidenceWorkflowService
from app.services.workflows.extraction import ExtractionWorkflowService
from app.services.workflows.intake import IntakeWorkflowService
from app.services.workflows.risk import RiskWorkflowService

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
    429: {"model": ErrorResponse, "description": "The workflow rate limit was reached."},
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
        CaseSubmission(
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
    extraction_workflows: Annotated[
        ExtractionWorkflowService, Depends(get_extraction_workflow_service)
    ],
    drafting_workflows: Annotated[DraftingWorkflowService, Depends(get_drafting_workflow_service)],
    risk_workflows: Annotated[RiskWorkflowService, Depends(get_risk_workflow_service)],
    settings: SettingsDependency,
    rate_limiter: RouteRateLimiterDependency,
) -> SuccessResponse[WorkflowRunData]:
    """Accept only fixed selectors; all model, state, and queue inputs stay server-owned."""

    await enforce_route_rate_limit(
        request,
        rate_limiter,
        RouteRateLimitPolicy(
            bucket="workflow",
            user_attempts=settings.workflow_rate_limit_user_attempts,
            origin_attempts=settings.workflow_rate_limit_origin_attempts,
            window_seconds=settings.workflow_rate_limit_window_seconds,
        ),
        user_id=str(principal.user_id),
    )

    run = (
        await workflows.start(principal, case_id)
        if payload.workflow == "intake"
        else (
            await evidence_workflows.start(principal, case_id)
            if payload.workflow == "evidence"
            else (
                await extraction_workflows.start(principal, case_id)
                if payload.workflow == "extraction"
                else (
                    await drafting_workflows.start(principal, case_id, payload.output_language)
                    if payload.workflow == "drafting"
                    else await risk_workflows.start(principal, case_id)
                )
            )
        )
    )
    return SuccessResponse(data=_workflow_run_data(run), meta=_meta(request))


@router.get(
    "/{case_id}/extraction/fields",
    response_model=SuccessResponse[ExtractedFieldListData],
    responses=_CASE_ERROR_RESPONSES,
    summary="List typed fields from the latest completed Extraction run",
)
async def list_extracted_fields(
    case_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    workflows: Annotated[ExtractionWorkflowService, Depends(get_extraction_workflow_service)],
) -> SuccessResponse[ExtractedFieldListData]:
    fields = await workflows.list_fields(principal, case_id)
    return SuccessResponse(
        data=ExtractedFieldListData(items=tuple(_extracted_field_data(field) for field in fields)),
        meta=_meta(request),
    )


@router.patch(
    "/{case_id}/extraction/fields/{field_id}",
    response_model=SuccessResponse[ExtractedFieldData],
    responses=_CASE_ERROR_RESPONSES,
    summary="Apply one schema-validated human edit to a latest Extraction field",
)
async def edit_extracted_field(
    case_id: UUID,
    field_id: UUID,
    payload: ExtractedFieldEditRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    workflows: Annotated[ExtractionWorkflowService, Depends(get_extraction_workflow_service)],
) -> SuccessResponse[ExtractedFieldData]:
    field = await workflows.edit_field(principal, case_id, field_id, payload.field_value)
    return SuccessResponse(data=_extracted_field_data(field), meta=_meta(request))


@router.get(
    "/{case_id}/draft",
    response_model=SuccessResponse[DraftData],
    responses=_CASE_ERROR_RESPONSES,
    summary="Read the latest protected original AI draft for one current-tenant case",
)
async def get_draft(
    case_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    workflows: Annotated[DraftingWorkflowService, Depends(get_drafting_workflow_service)],
) -> SuccessResponse[DraftData]:
    """This is intentionally read-only; later phases own human edits and approval."""

    record = await workflows.get_draft(principal, case_id)
    metadata = record.message.structured_output or {}
    language_value = metadata.get("language")
    draft_kind_value = metadata.get("draft_kind")
    return SuccessResponse(
        data=DraftData(
            workflow_run_id=record.message.workflow_run_id,
            content=record.message.content,
            language=OutputLanguage(language_value)
            if isinstance(language_value, str)
            else OutputLanguage.NB,
            draft_kind=DraftKind(draft_kind_value)
            if isinstance(draft_kind_value, str)
            else DraftKind.RESPONSE,
            citations=tuple(
                DraftCitationData(
                    citation_label=source.citation_label,
                    document_id=source.document_id,
                    chunk_id=source.chunk_id,
                )
                for source in record.sources
            ),
        ),
        meta=_meta(request),
    )


@router.get(
    "/{case_id}/risk-assessment",
    response_model=SuccessResponse[RiskAssessmentData],
    responses=_CASE_ERROR_RESPONSES,
    summary="Read the latest safe final risk assessment for one current-tenant case",
)
async def get_risk_assessment(
    case_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    workflows: Annotated[RiskWorkflowService, Depends(get_risk_workflow_service)],
) -> SuccessResponse[RiskAssessmentData]:
    """This is read-only: Phase 22 owns approval decisions and review actions."""

    assessment = await workflows.get_latest_assessment(principal, case_id)
    return SuccessResponse(
        data=RiskAssessmentData(
            workflow_run_id=assessment.workflow_run_id,
            risk_level=assessment.result.risk_level,
            risk_reasons=assessment.result.risk_reasons,
            requires_approval=assessment.result.requires_approval,
            safe_next_state=assessment.result.safe_next_state,
        ),
        meta=_meta(request),
    )


@router.get(
    "/{case_id}/audit",
    response_model=SuccessResponse[AuditEventListData],
    responses=_CASE_ERROR_RESPONSES,
    summary="List immutable audit events for one readable current-tenant case",
)
async def list_case_audit_events(
    case_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    audit: AuditServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[AuditEventListData]:
    """Apply case-read policy before a server-owned case filter is sent to the audit service."""

    page = await audit.list_for_case(
        principal,
        case_id,
        pagination=Pagination(limit=limit, offset=offset),
    )
    return SuccessResponse(data=audit_page_data(page), meta=_meta(request))


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


def _extracted_field_data(field: object) -> ExtractedFieldData:
    """Return the dedicated typed business-field view, never a graph snapshot."""

    from agent_orchestrator.config import AgentSettings
    from agent_orchestrator.graphs.extraction_types import (
        ConfidenceBand,
        ExtractionFieldKind,
        validate_extraction_value,
    )

    from app.db.repositories.extraction import ExtractedFieldWithDocument

    view = cast(ExtractedFieldWithDocument, field)
    record = view.field
    kind = ExtractionFieldKind(record.field_name)
    value = validate_extraction_value(kind, record.field_value)
    confidence = float(record.confidence) if record.confidence is not None else 0.0
    return ExtractedFieldData(
        field_id=record.id,
        workflow_run_id=record.workflow_run_id,
        field_kind=kind,
        field_value=value,
        confidence_band=(
            ConfidenceBand.HIGH
            if confidence >= AgentSettings().extraction_confidence_threshold
            else ConfidenceBand.LOW
        ),
        source_document_id=view.document_id,
        source_chunk_id=record.source_chunk_id,
        human_edited=record.human_edited,
        updated_at=record.updated_at,
    )
