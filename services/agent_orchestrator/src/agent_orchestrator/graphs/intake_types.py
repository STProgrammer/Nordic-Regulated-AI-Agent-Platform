"""Closed domain vocabulary for the first business graph: Intake."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from agent_orchestrator.state.case_state import CaseWorkflowState


class IntakeLanguage(StrEnum):
    NORWEGIAN_BOKMAL = "nb"
    ENGLISH = "en"
    UNKNOWN = "unknown"


class IntakeDomain(StrEnum):
    PUBLIC_SECTOR = "public_sector"
    BANKING_COMPLIANCE = "banking_compliance"
    ENERGY_OPERATIONS = "energy_operations"
    INTERNAL_POLICY = "internal_policy"


class IntakeCaseType(StrEnum):
    CASE_SUPPORT = "case_support"
    COMPLIANCE_REVIEW = "compliance_review"
    OPERATIONAL_INCIDENT = "operational_incident"
    POLICY_QUESTION = "policy_question"
    DOCUMENT_INTELLIGENCE = "document_intelligence"
    UNKNOWN = "unknown"


class IntakePriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class PreliminaryRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PiiCategory(StrEnum):
    EMAIL = "email"
    NORWEGIAN_NATIONAL_IDENTIFIER = "norwegian_national_identifier"
    PHONE = "phone"


class InjectionSignal(StrEnum):
    INSTRUCTION_OVERRIDE = "instruction_override"


class SuggestedWorkflow(StrEnum):
    EVIDENCE = "evidence"
    EXTRACTION = "extraction"
    EVIDENCE_THEN_DRAFT = "evidence_then_draft"
    MANUAL_REVIEW = "manual_review"


class ClassificationSource(StrEnum):
    MODEL = "model"
    HUMAN_CORRECTED = "human_corrected"


class ClassifierOutput(BaseModel):
    """Strict provider output; free-form rationales are intentionally excluded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_type: IntakeCaseType
    recommended_domain: IntakeDomain
    confidence: Annotated[float, Field(ge=0, le=1)]
    reason_codes: tuple[str, ...] = Field(default=(), max_length=6)


class LanguageDetectionResult(BaseModel):
    """A bounded language signal from a deterministic detector."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: IntakeLanguage
    confidence: Annotated[float, Field(ge=0, le=1)]


class IntakeWorkflowState(CaseWorkflowState):
    """Intake state contains only bounded signals; raw case content remains in dependencies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    declared_language: IntakeLanguage
    submitted_domain: IntakeDomain
    priority: IntakePriority
    detected_language: IntakeLanguage = IntakeLanguage.UNKNOWN
    detected_language_confident: bool = False
    language_mismatch: bool = False
    classification_case_type: IntakeCaseType = IntakeCaseType.UNKNOWN
    recommended_domain: IntakeDomain | None = None
    classification_confidence: Annotated[float | None, Field(default=None, ge=0, le=1)] = None
    low_confidence: bool = True
    classification_reason_codes: tuple[str, ...] = ()
    pii_detected: bool = False
    pii_categories: tuple[PiiCategory, ...] = ()
    prompt_injection_detected: bool = False
    prompt_injection_categories: tuple[InjectionSignal, ...] = ()
    preliminary_risk_level: PreliminaryRiskLevel = PreliminaryRiskLevel.MEDIUM
    preliminary_risk_reasons: tuple[str, ...] = ()
    suggested_workflow: SuggestedWorkflow = SuggestedWorkflow.MANUAL_REVIEW
    suggested_workflow_reasons: tuple[str, ...] = ()
    classification_source: ClassificationSource = ClassificationSource.MODEL
    node_count: Annotated[int, Field(ge=0, le=8)] = 0
