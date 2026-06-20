"""Closed public schemas for starting, viewing, and correcting Intake only."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.schemas.cases import CaseDomain, CaseRiskLevel


class IntakeCaseType(StrEnum):
    CASE_SUPPORT = "case_support"
    COMPLIANCE_REVIEW = "compliance_review"
    OPERATIONAL_INCIDENT = "operational_incident"
    POLICY_QUESTION = "policy_question"
    DOCUMENT_INTELLIGENCE = "document_intelligence"
    UNKNOWN = "unknown"


class WorkflowRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DetectedLanguage(StrEnum):
    NORWEGIAN_BOKMAL = "nb"
    ENGLISH = "en"
    UNKNOWN = "unknown"


class SuggestedWorkflow(StrEnum):
    EVIDENCE = "evidence"
    EXTRACTION = "extraction"
    EVIDENCE_THEN_DRAFT = "evidence_then_draft"
    MANUAL_REVIEW = "manual_review"


class IntakeCorrectionReason(StrEnum):
    CLASSIFICATION_REVIEW = "classification_review"
    DOMAIN_REVIEW = "domain_review"
    USER_CONTEXT = "user_context"


class IntakeStartRequest(BaseModel):
    """Exactly one supported server-owned graph selector."""

    model_config = ConfigDict(extra="forbid")

    workflow: Literal["intake"]


class IntakeCorrectionRequest(BaseModel):
    """Closed human correction without risk or free-text changes."""

    model_config = ConfigDict(extra="forbid")

    case_type: IntakeCaseType
    domain: CaseDomain
    reason_code: IntakeCorrectionReason | None = None


class IntakeResultData(BaseModel):
    """Allowlisted persisted Intake signals; no snapshot/trace/provider payload escapes."""

    model_config = ConfigDict(frozen=True)

    declared_language: DetectedLanguage | None = None
    detected_language: DetectedLanguage | None = None
    language_mismatch: bool | None = None
    case_type: IntakeCaseType | None = None
    recommended_domain: CaseDomain | None = None
    low_confidence: bool | None = None
    pii_detected: bool | None = None
    prompt_injection_detected: bool | None = None
    preliminary_risk_level: CaseRiskLevel | None = None
    preliminary_risk_reasons: tuple[str, ...] = ()
    preliminary_approval_required: bool | None = None
    suggested_workflow: SuggestedWorkflow | None = None
    suggested_workflow_reasons: tuple[str, ...] = ()
    classification_source: Literal["model", "human_corrected"] | None = None


class WorkflowRunData(BaseModel):
    """Safe status view for a user's current-tenant Intake run."""

    model_config = ConfigDict(frozen=True)

    workflow_run_id: UUID
    workflow: Literal["intake"]
    status: WorkflowRunStatus
    started_at: datetime
    finished_at: datetime | None
    intake: IntakeResultData | None = None
