"""Closed public contracts for the Phase-22 human review boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from agent_orchestrator.graphs.approval_types import ApprovalLifecycle, ReviewerDecision
from agent_orchestrator.graphs.risk_types import FinalRiskLevel, RiskReason
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.cases import CaseStatus


def _optional_comment(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("reviewer_comment must not be blank.")
    return normalized


class ApprovalCommentRequest(BaseModel):
    """A bounded optional reviewer explanation with no browser-owned workflow fields."""

    model_config = ConfigDict(extra="forbid")

    reviewer_comment: Annotated[str | None, Field(default=None, max_length=2_000)] = None

    @field_validator("reviewer_comment")
    @classmethod
    def validate_comment(cls, value: str | None) -> str | None:
        return _optional_comment(value)


class EditAndApproveRequest(ApprovalCommentRequest):
    """The only action permitted to carry separately retained final human wording."""

    final_text: Annotated[str, Field(min_length=1, max_length=20_000)]

    @field_validator("final_text")
    @classmethod
    def validate_final_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("final_text must not be blank.")
        return normalized


class ReassignApprovalRequest(BaseModel):
    """An explicit current-tenant assignment target, without any decision payload."""

    model_config = ConfigDict(extra="forbid")

    assigned_user_id: UUID


class ApprovalSourceData(BaseModel):
    """Identifier-only link for the existing protected bounded source-context endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    citation_label: str
    document_id: UUID
    chunk_id: UUID


class ApprovalExtractedFieldData(BaseModel):
    """The decision-relevant typed field view; raw workflow traces remain unavailable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field_id: UUID
    field_kind: str
    field_value: dict[str, object]
    source_document_id: UUID | None
    source_chunk_id: UUID | None
    human_edited: bool


class ApprovalQueueItemData(BaseModel):
    """Small deterministic queue projection that excludes draft/source content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_id: UUID
    case_id: UUID
    case_number: str
    case_title: str
    case_status: CaseStatus
    risk_level: FinalRiskLevel
    approval_status: ApprovalLifecycle
    assigned_user_id: UUID | None
    inserted_at: datetime


class ApprovalQueueData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[ApprovalQueueItemData, ...]
    limit: int
    offset: int
    total: int
    has_more: bool


class ApprovalReviewPacketData(BaseModel):
    """Protected decision packet; trace/provider details and source excerpts are absent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_id: UUID
    case_id: UUID
    case_number: str
    case_title: str
    case_status: CaseStatus
    risk_level: FinalRiskLevel
    risk_reasons: tuple[RiskReason, ...]
    approval_status: ApprovalLifecycle
    workflow_status: Literal["queued", "running", "waiting_for_human_review", "completed", "failed"]
    assigned_user_id: UUID | None
    reviewer_user_id: UUID | None
    reviewer_comment: str | None
    decision: ReviewerDecision | None
    decision_at: datetime | None
    ai_draft: str
    final_text: str | None
    sources: tuple[ApprovalSourceData, ...]
    extracted_fields: tuple[ApprovalExtractedFieldData, ...]


class ApprovalActionResultData(BaseModel):
    """Safe post-submit state; terminal resolution remains worker-owned and asynchronous."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_id: UUID
    approval_status: ApprovalLifecycle
    decision: ReviewerDecision | None
    case_id: UUID
    workflow_status: Literal["queued", "running", "waiting_for_human_review", "completed", "failed"]
