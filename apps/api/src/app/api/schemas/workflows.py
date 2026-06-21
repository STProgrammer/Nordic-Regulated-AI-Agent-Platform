"""Closed public schemas for starting, viewing, and correcting Intake only."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from agent_orchestrator.graphs.drafting_types import DraftKind, OutputLanguage
from agent_orchestrator.graphs.extraction_types import (
    ConfidenceBand,
    ExtractionFieldKind,
    ExtractionValue,
)
from pydantic import BaseModel, ConfigDict, Field

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
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
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


class EvidenceStartRequest(BaseModel):
    """Closed Evidence selector; query, source selection, and provider stay server-owned."""

    model_config = ConfigDict(extra="forbid")

    workflow: Literal["evidence"]


class ExtractionStartRequest(BaseModel):
    """Closed extraction selector; Evidence source choice and schema remain server-owned."""

    model_config = ConfigDict(extra="forbid")

    workflow: Literal["extraction"]


class DraftingStartRequest(BaseModel):
    """Closed Drafting selector with an optional server-validated display language."""

    model_config = ConfigDict(extra="forbid")

    workflow: Literal["drafting"]
    output_language: OutputLanguage | None = None


WorkflowStartRequest = Annotated[
    IntakeStartRequest | EvidenceStartRequest | ExtractionStartRequest | DraftingStartRequest,
    Field(discriminator="workflow"),
]


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


class EvidenceReasonCode(StrEnum):
    NO_ELIGIBLE_SOURCES = "no_eligible_sources"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"


class EvidenceSourceData(BaseModel):
    """Safe identifier-only source reference for the existing authorized context endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    citation_label: str
    document_id: UUID
    chunk_id: UUID
    source_status: Literal["approved"]
    warning_codes: tuple[str, ...] = ()


class EvidenceResultData(BaseModel):
    """Allowlisted Evidence outcome; query, excerpts, scores, traces, and errors are absent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: Literal["completed", "needs_more_evidence"] | None = None
    sufficient: bool | None = None
    contradiction_detected: bool | None = None
    reason_codes: tuple[EvidenceReasonCode, ...] = ()
    citation_labels: tuple[str, ...] = ()
    sources: tuple[EvidenceSourceData, ...] = ()


class ExtractionResultData(BaseModel):
    """Safe Extraction status data; typed business values are available only from the field API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_available: bool | None = None
    extraction_schema: str | None = None
    extracted_field_count: int | None = None
    low_confidence_field_count: int | None = None


class DraftingResultData(BaseModel):
    """Safe Drafting lifecycle signals; text is available only on its dedicated read route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_available: bool | None = None
    draft_available: bool | None = None
    citation_count: int | None = None
    output_language: OutputLanguage | None = None
    draft_kind: DraftKind | None = None
    reason_codes: tuple[str, ...] = ()


class DraftCitationData(BaseModel):
    """One stable source reference for an already-authorized protected original draft."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    citation_label: str
    document_id: UUID
    chunk_id: UUID


class DraftData(BaseModel):
    """The limited protected presentation shape for one immutable original AI draft."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_run_id: UUID
    content: str
    language: OutputLanguage
    draft_kind: DraftKind
    citations: tuple[DraftCitationData, ...]


class ExtractedFieldData(BaseModel):
    """One source-linked typed business field from the latest completed extraction run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field_id: UUID
    workflow_run_id: UUID
    field_kind: ExtractionFieldKind
    field_value: ExtractionValue
    confidence_band: ConfidenceBand
    source_document_id: UUID | None
    source_chunk_id: UUID | None
    human_edited: bool
    updated_at: datetime


class ExtractedFieldListData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[ExtractedFieldData, ...]


class ExtractedFieldEditRequest(BaseModel):
    """Only the pre-existing field's typed value may change; kind/source/run stay server-owned."""

    model_config = ConfigDict(extra="forbid")

    field_value: ExtractionValue


class WorkflowRunData(BaseModel):
    """Safe status view for a supported current-tenant workflow run."""

    model_config = ConfigDict(frozen=True)

    workflow_run_id: UUID
    workflow: Literal["intake", "evidence", "extraction", "drafting"]
    status: WorkflowRunStatus
    started_at: datetime
    finished_at: datetime | None
    intake: IntakeResultData | None = None
    evidence: EvidenceResultData | None = None
    extraction: ExtractionResultData | None = None
    drafting: DraftingResultData | None = None
