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
from agent_orchestrator.graphs.risk_types import FinalRiskLevel, RiskReason, RiskSafeNextState
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
    WAITING_FOR_HUMAN_REVIEW = "waiting_for_human_review"
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


class RiskComplianceStartRequest(BaseModel):
    """Closed final-risk selector; all policy inputs remain server owned."""

    model_config = ConfigDict(extra="forbid")

    workflow: Literal["risk_compliance"]


WorkflowStartRequest = Annotated[
    IntakeStartRequest
    | EvidenceStartRequest
    | ExtractionStartRequest
    | DraftingStartRequest
    | RiskComplianceStartRequest,
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


class RiskResultData(BaseModel):
    """Safe lifecycle summary for the closed Risk and Compliance workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    final_risk_level: FinalRiskLevel | None = None
    risk_reasons: tuple[RiskReason, ...] = ()
    requires_approval: bool | None = None
    safe_next_state: RiskSafeNextState | None = None


class RiskAssessmentData(BaseModel):
    """Read-only latest final assessment; policy internals stay private."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_run_id: UUID
    risk_level: FinalRiskLevel
    risk_reasons: tuple[RiskReason, ...]
    requires_approval: bool
    safe_next_state: RiskSafeNextState


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
    workflow: Literal[
        "intake", "evidence", "extraction", "drafting", "risk_compliance", "human_approval"
    ]
    status: WorkflowRunStatus
    started_at: datetime
    finished_at: datetime | None
    intake: IntakeResultData | None = None
    evidence: EvidenceResultData | None = None
    extraction: ExtractionResultData | None = None
    drafting: DraftingResultData | None = None
    risk_compliance: RiskResultData | None = None


class WorkflowTraceHeaderData(BaseModel):
    """Safe workflow lifecycle and aggregate accounting for one trace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_run_id: UUID
    workflow_name: str = Field(min_length=1, max_length=255)
    workflow_version: str = Field(min_length=1, max_length=100)
    case_id: UUID
    status: str = Field(min_length=1, max_length=50)
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    total_cost_estimate: float | None = Field(default=None, ge=0)
    final_error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,99}$")


class WorkflowTraceNodeData(BaseModel):
    """One sanitized graph-node attempt; summaries contain only safe state shape."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_run_id: UUID
    node_name: str = Field(min_length=1, max_length=255)
    status: str = Field(min_length=1, max_length=50)
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(ge=0)
    input_summary: dict[str, object] = Field(default_factory=dict)
    output_summary: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,99}$")


class WorkflowTraceToolCallData(BaseModel):
    """Tool identity/outcome metadata without any input or output body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_call_id: UUID
    node_run_id: UUID | None
    tool_name: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=50)
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(ge=0)
    input_summary: dict[str, object] = Field(default_factory=dict)
    output_summary: dict[str, object] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,99}$")


class WorkflowTraceModelCallData(BaseModel):
    """Provider accounting metadata without prompts or provider request/response data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_usage_id: UUID
    provider: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=255)
    operation: str = Field(min_length=1, max_length=100)
    success: bool
    token_input: int | None = Field(default=None, ge=0)
    token_output: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,99}$")


class WorkflowTraceSourceData(BaseModel):
    """A governed source link that remains subject to the existing context endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_status: Literal["available", "unavailable"]
    citation_label: str | None = Field(default=None, max_length=160)
    document_id: UUID | None = None
    chunk_id: UUID | None = None
    rank: int | None = Field(default=None, ge=0)
    retrieval_method: str | None = Field(default=None, max_length=100)


class WorkflowTraceData(BaseModel):
    """The complete safe trace projection for one readable workflow run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    header: WorkflowTraceHeaderData
    final_state: dict[str, object] = Field(default_factory=dict)
    nodes: tuple[WorkflowTraceNodeData, ...] = ()
    tool_calls: tuple[WorkflowTraceToolCallData, ...] = ()
    model_calls: tuple[WorkflowTraceModelCallData, ...] = ()
    sources: tuple[WorkflowTraceSourceData, ...] = ()
    unavailable_source_count: int = Field(default=0, ge=0)
