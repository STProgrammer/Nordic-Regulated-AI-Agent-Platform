"""Closed status and low-confidence correction operations for Intake."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from agent_orchestrator.graphs.intake_types import (
    IntakeCaseType as CoreIntakeCaseType,
)
from agent_orchestrator.graphs.intake_types import (
    IntakeDomain as CoreIntakeDomain,
)
from fastapi import APIRouter, Depends, Request

from app.api.dependencies import CurrentPrincipalDependency, get_intake_workflow_service
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.api.schemas.workflows import (
    EvidenceResultData,
    ExtractionResultData,
    IntakeCorrectionRequest,
    IntakeResultData,
    WorkflowRunData,
    WorkflowRunStatus,
)
from app.db.models.workflow import WorkflowRun
from app.services.errors import NotFoundError
from app.services.workflows.intake import IntakeCorrection, IntakeWorkflowService

PREFIX = "/workflows"
TAG = "Workflows"
DESCRIPTION = "Closed Intake and Evidence workflow status plus Intake-only correction operations."

router = APIRouter()

_WORKFLOW_ERRORS = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "The current role is not allowed."},
    404: {"model": ErrorResponse, "description": "The workflow run was not found."},
    409: {"model": ErrorResponse, "description": "The workflow run cannot be corrected."},
}


@router.get(
    "/{workflow_run_id}",
    response_model=SuccessResponse[WorkflowRunData],
    responses=_WORKFLOW_ERRORS,
    summary="Get a safe current-tenant supported workflow status",
)
async def get_workflow_run(
    workflow_run_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    workflows: Annotated[IntakeWorkflowService, Depends(get_intake_workflow_service)],
) -> SuccessResponse[WorkflowRunData]:
    """Expose only an allowlisted workflow projection, never state, query, or node trace."""

    run = await workflows.get_for_principal(principal, workflow_run_id)
    return SuccessResponse(data=workflow_run_data(run), meta=_meta(request))


@router.post(
    "/{workflow_run_id}/intake/correction",
    response_model=SuccessResponse[WorkflowRunData],
    responses=_WORKFLOW_ERRORS,
    summary="Record one closed human correction for the latest low-confidence Intake run",
)
async def correct_intake_classification(
    workflow_run_id: UUID,
    payload: IntakeCorrectionRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    workflows: Annotated[IntakeWorkflowService, Depends(get_intake_workflow_service)],
) -> SuccessResponse[WorkflowRunData]:
    """Do not expose a generic workflow mutation or risk/approval override."""

    run = await workflows.correct(
        principal,
        workflow_run_id,
        IntakeCorrection(
            case_type=CoreIntakeCaseType(payload.case_type.value),
            domain=CoreIntakeDomain(payload.domain.value),
            reason_code=payload.reason_code.value if payload.reason_code is not None else None,
        ),
    )
    return SuccessResponse(data=workflow_run_data(run), meta=_meta(request))


def workflow_run_data(run: object) -> WorkflowRunData:
    """Map only safe snapshot keys into the public limited status view."""

    workflow_run = cast(WorkflowRun, run)
    snapshot = workflow_run.state_snapshot
    if workflow_run.workflow_name not in {"intake", "evidence", "extraction"}:
        raise NotFoundError("Workflow run")
    intake = (
        _intake_data(snapshot)
        if workflow_run.workflow_name == "intake" and workflow_run.status in {"completed", "failed"}
        else None
    )
    evidence = (
        _evidence_data(snapshot)
        if workflow_run.workflow_name == "evidence"
        and workflow_run.status in {"completed", "needs_more_evidence", "failed"}
        else None
    )
    extraction = (
        _extraction_data(snapshot)
        if workflow_run.workflow_name == "extraction"
        and workflow_run.status in {"completed", "needs_more_evidence", "failed"}
        else None
    )
    return WorkflowRunData(
        workflow_run_id=workflow_run.id,
        workflow=cast(Literal["intake", "evidence", "extraction"], workflow_run.workflow_name),
        status=WorkflowRunStatus(workflow_run.status),
        started_at=workflow_run.started_at,
        finished_at=workflow_run.finished_at,
        intake=intake,
        evidence=evidence,
        extraction=extraction,
    )


def _intake_data(snapshot: dict[str, object]) -> IntakeResultData | None:
    if not snapshot:
        return None
    data: dict[str, object] = {}
    mapping = {
        "declared_language": "declared_language",
        "detected_language": "detected_language",
        "language_mismatch": "language_mismatch",
        "classification_case_type": "case_type",
        "recommended_domain": "recommended_domain",
        "low_confidence": "low_confidence",
        "pii_detected": "pii_detected",
        "prompt_injection_detected": "prompt_injection_detected",
        "preliminary_risk_level": "preliminary_risk_level",
        "preliminary_risk_reasons": "preliminary_risk_reasons",
        "approval_required": "preliminary_approval_required",
        "suggested_workflow": "suggested_workflow",
        "suggested_workflow_reasons": "suggested_workflow_reasons",
        "classification_source": "classification_source",
    }
    for source, target in mapping.items():
        value = snapshot.get(source)
        if value is not None:
            data[target] = value
    return IntakeResultData.model_validate(data) if data else None


def _evidence_data(snapshot: dict[str, object]) -> EvidenceResultData | None:
    """Select only the deliberately safe Evidence package presentation keys."""

    if not snapshot:
        return None
    data: dict[str, object] = {}
    mapping = {
        "evidence_outcome": "outcome",
        "evidence_sufficient": "sufficient",
        "contradiction_detected": "contradiction_detected",
        "reason_codes": "reason_codes",
        "citation_labels": "citation_labels",
        "evidence_sources": "sources",
    }
    for source, target in mapping.items():
        value = snapshot.get(source)
        if value is not None:
            data[target] = value
    return EvidenceResultData.model_validate(data) if data else None


def _extraction_data(snapshot: dict[str, object]) -> ExtractionResultData | None:
    """Map only aggregate safe extraction lifecycle signals into the status DTO."""

    if not snapshot:
        return None
    data: dict[str, object] = {}
    mapping = {
        "evidence_available": "evidence_available",
        "extraction_schema": "extraction_schema",
        "extracted_field_count": "extracted_field_count",
        "low_confidence_field_count": "low_confidence_field_count",
    }
    for source, target in mapping.items():
        value = snapshot.get(source)
        if value is not None:
            data[target] = value
    return ExtractionResultData.model_validate(data) if data else None


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
