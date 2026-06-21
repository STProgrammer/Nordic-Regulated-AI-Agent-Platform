"""Protected queue, review-packet, and explicit human decision operations."""

from typing import Annotated, Literal, cast
from uuid import UUID

from agent_orchestrator.graphs.approval_types import ApprovalLifecycle, ReviewerDecision
from agent_orchestrator.graphs.risk_types import FinalRiskLevel, RiskReason
from fastapi import APIRouter, Query, Request

from app.api.dependencies import ApprovalWorkflowServiceDependency, CurrentPrincipalDependency
from app.api.schemas.approvals import (
    ApprovalActionResultData,
    ApprovalCommentRequest,
    ApprovalExtractedFieldData,
    ApprovalQueueData,
    ApprovalQueueItemData,
    ApprovalReviewPacketData,
    ApprovalSourceData,
    EditAndApproveRequest,
    ReassignApprovalRequest,
)
from app.api.schemas.cases import CaseStatus
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.services.approvals.service import (
    ApprovalActionSubmission,
    ApprovalQueueItem,
    ApprovalReviewPacket,
)

PREFIX = "/approvals"
TAG = "Approvals"
DESCRIPTION = "Tenant-scoped human review queue, packet, assignments, and explicit decisions."

router = APIRouter()

_APPROVAL_ERRORS = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "The current role is not allowed."},
    404: {"model": ErrorResponse, "description": "The approval was not found."},
    409: {"model": ErrorResponse, "description": "The approval cannot be changed."},
    503: {"model": ErrorResponse, "description": "Workflow processing is unavailable."},
}


@router.get(
    "",
    response_model=SuccessResponse[ApprovalQueueData],
    responses=_APPROVAL_ERRORS,
    summary="List pending human review work in deterministic queue order",
)
async def list_approvals(
    request: Request,
    principal: CurrentPrincipalDependency,
    approvals: ApprovalWorkflowServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[ApprovalQueueData]:
    items, total = await approvals.list_queue(principal, limit=limit, offset=offset)
    data_items = tuple(_queue_item_data(item) for item in items)
    return SuccessResponse(
        data=ApprovalQueueData(
            items=data_items,
            limit=limit,
            offset=offset,
            total=total,
            has_more=offset + len(data_items) < total,
        ),
        meta=_meta(request),
    )


@router.get(
    "/{approval_id}",
    response_model=SuccessResponse[ApprovalReviewPacketData],
    responses=_APPROVAL_ERRORS,
    summary="Read one protected human review packet",
)
async def get_approval(
    approval_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    approvals: ApprovalWorkflowServiceDependency,
) -> SuccessResponse[ApprovalReviewPacketData]:
    packet = await approvals.get_review_packet(principal, approval_id)
    return SuccessResponse(data=_packet_data(packet), meta=_meta(request))


@router.post(
    "/{approval_id}/approve",
    response_model=SuccessResponse[ApprovalActionResultData],
    responses=_APPROVAL_ERRORS,
    summary="Submit an unchanged-draft approval for worker-owned resume",
)
async def approve(
    approval_id: UUID,
    payload: ApprovalCommentRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    approvals: ApprovalWorkflowServiceDependency,
) -> SuccessResponse[ApprovalActionResultData]:
    result = await approvals.submit_decision(
        principal,
        approval_id,
        decision=ReviewerDecision.APPROVE,
        reviewer_comment=payload.reviewer_comment,
    )
    return SuccessResponse(data=_action_data(result), meta=_meta(request))


@router.post(
    "/{approval_id}/edit-and-approve",
    response_model=SuccessResponse[ApprovalActionResultData],
    responses=_APPROVAL_ERRORS,
    summary="Submit separate human final text and approve for worker-owned resume",
)
async def edit_and_approve(
    approval_id: UUID,
    payload: EditAndApproveRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    approvals: ApprovalWorkflowServiceDependency,
) -> SuccessResponse[ApprovalActionResultData]:
    result = await approvals.submit_decision(
        principal,
        approval_id,
        decision=ReviewerDecision.EDIT_AND_APPROVE,
        reviewer_comment=payload.reviewer_comment,
        final_text=payload.final_text,
    )
    return SuccessResponse(data=_action_data(result), meta=_meta(request))


@router.post(
    "/{approval_id}/reject",
    response_model=SuccessResponse[ApprovalActionResultData],
    responses=_APPROVAL_ERRORS,
    summary="Reject a review packet for worker-owned controlled resolution",
)
async def reject(
    approval_id: UUID,
    payload: ApprovalCommentRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    approvals: ApprovalWorkflowServiceDependency,
) -> SuccessResponse[ApprovalActionResultData]:
    result = await approvals.submit_decision(
        principal,
        approval_id,
        decision=ReviewerDecision.REJECT,
        reviewer_comment=payload.reviewer_comment,
    )
    return SuccessResponse(data=_action_data(result), meta=_meta(request))


@router.post(
    "/{approval_id}/request-more-evidence",
    response_model=SuccessResponse[ApprovalActionResultData],
    responses=_APPROVAL_ERRORS,
    summary="Request more evidence without automatically starting another workflow",
)
async def request_more_evidence(
    approval_id: UUID,
    payload: ApprovalCommentRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    approvals: ApprovalWorkflowServiceDependency,
) -> SuccessResponse[ApprovalActionResultData]:
    result = await approvals.submit_decision(
        principal,
        approval_id,
        decision=ReviewerDecision.REQUEST_MORE_EVIDENCE,
        reviewer_comment=payload.reviewer_comment,
    )
    return SuccessResponse(data=_action_data(result), meta=_meta(request))


@router.post(
    "/{approval_id}/reassign",
    response_model=SuccessResponse[ApprovalActionResultData],
    responses=_APPROVAL_ERRORS,
    summary="Reassign a pending review to an active approval-capable tenant user",
)
async def reassign(
    approval_id: UUID,
    payload: ReassignApprovalRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    approvals: ApprovalWorkflowServiceDependency,
) -> SuccessResponse[ApprovalActionResultData]:
    approval = await approvals.reassign(
        principal, approval_id, assigned_user_id=payload.assigned_user_id
    )
    return SuccessResponse(
        data=ApprovalActionResultData(
            approval_id=approval.id,
            approval_status=ApprovalLifecycle(approval.status),
            decision=ReviewerDecision(approval.decision) if approval.decision is not None else None,
            case_id=approval.case_id,
            workflow_status="waiting_for_human_review",
        ),
        meta=_meta(request),
    )


def _queue_item_data(item: ApprovalQueueItem) -> ApprovalQueueItemData:
    risk_level = FinalRiskLevel(item.case.risk_level or "medium")
    return ApprovalQueueItemData(
        approval_id=item.approval.id,
        case_id=item.case.id,
        case_number=item.case.case_number,
        case_title=item.case.title,
        case_status=CaseStatus(item.case.status),
        risk_level=risk_level,
        approval_status=ApprovalLifecycle(item.approval.status),
        assigned_user_id=item.approval.assigned_user_id,
        inserted_at=item.approval.inserted_at,
    )


def _packet_data(packet: ApprovalReviewPacket) -> ApprovalReviewPacketData:
    codes = packet.risk.risk_reasons.get("codes")
    risk_reasons = tuple(RiskReason(code) for code in codes) if isinstance(codes, list) else ()
    return ApprovalReviewPacketData(
        approval_id=packet.approval.id,
        case_id=packet.case.id,
        case_number=packet.case.case_number,
        case_title=packet.case.title,
        case_status=CaseStatus(packet.case.status),
        risk_level=FinalRiskLevel(packet.risk.risk_level),
        risk_reasons=risk_reasons,
        approval_status=ApprovalLifecycle(packet.approval.status),
        workflow_status=cast(
            Literal["queued", "running", "waiting_for_human_review", "completed", "failed"],
            packet.workflow_status,
        ),
        assigned_user_id=packet.approval.assigned_user_id,
        reviewer_user_id=packet.approval.reviewer_user_id,
        reviewer_comment=packet.approval.reviewer_comment,
        decision=(
            ReviewerDecision(packet.approval.decision)
            if packet.approval.decision is not None
            else None
        ),
        decision_at=packet.approval.decision_at,
        ai_draft=packet.approval.ai_draft or "",
        final_text=packet.approval.final_text,
        sources=tuple(
            ApprovalSourceData(
                citation_label=source.citation_label,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
            )
            for source in packet.sources
        ),
        extracted_fields=tuple(
            ApprovalExtractedFieldData(
                field_id=field.field_id,
                field_kind=field.field_kind,
                field_value=field.field_value,
                source_document_id=field.source_document_id,
                source_chunk_id=field.source_chunk_id,
                human_edited=field.human_edited,
            )
            for field in packet.extracted_fields
        ),
    )


def _action_data(result: ApprovalActionSubmission) -> ApprovalActionResultData:
    return ApprovalActionResultData(
        approval_id=result.approval.id,
        approval_status=ApprovalLifecycle(result.approval.status),
        decision=(
            ReviewerDecision(result.approval.decision)
            if result.approval.decision is not None
            else None
        ),
        case_id=result.approval.case_id,
        workflow_status=cast(
            Literal["queued", "running", "waiting_for_human_review", "completed", "failed"],
            result.workflow_status,
        ),
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
