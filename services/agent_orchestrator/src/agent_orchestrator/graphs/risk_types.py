"""Closed types for the deterministic Risk and Compliance graph."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from agent_orchestrator.state.case_state import CaseWorkflowState


class FinalRiskLevel(StrEnum):
    """The final vocabulary shared with the Case risk projection."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskSafeNextState(StrEnum):
    """Routing-only outcomes; this phase neither creates nor resumes approval work."""

    ASSESSMENT_COMPLETE = "assessment_complete"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class RiskReason(StrEnum):
    """Closed, content-free explanations safe for status, audit, and presentation."""

    PII_DETECTED = "pii_detected"
    SENSITIVE_DOMAIN = "sensitive_domain"
    WEAK_EVIDENCE = "weak_evidence"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    MISSING_REQUIRED_SOURCE = "missing_required_source"
    LOW_CONFIDENCE = "low_confidence"
    HIGH_IMPACT_ACTION = "high_impact_action"
    POLICY_CONFLICT = "policy_conflict"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"


class RiskSignals(BaseModel):
    """Trusted, bounded worker input.  Text, identifiers, and policy controls are absent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pii_detected: bool = False
    sensitive_domain: bool = False
    weak_evidence: bool = False
    contradictory_evidence: bool = False
    missing_required_source: bool = False
    low_confidence: bool = False
    high_impact_action: bool = False
    policy_conflict: bool = False
    prompt_injection_detected: bool = False


class RiskAssessmentResult(BaseModel):
    """The final safe assessment shape persisted and exposed by API adapters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_level: FinalRiskLevel
    risk_reasons: tuple[RiskReason, ...] = Field(default=(), max_length=9)
    requires_approval: bool
    safe_next_state: RiskSafeNextState


class RiskWorkflowState(CaseWorkflowState):
    """Only closed risk signals and results may enter durable graph state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pii_detected: bool = False
    sensitive_domain: bool = False
    weak_evidence: bool = False
    contradictory_evidence: bool = False
    missing_required_source: bool = False
    low_confidence: bool = False
    high_impact_action: bool = False
    policy_conflict: bool = False
    prompt_injection_detected: bool = False
    final_risk_level: FinalRiskLevel | None = None
    safe_next_state: RiskSafeNextState | None = None
    reason_codes: tuple[RiskReason, ...] = Field(default=(), max_length=9)
    node_count: Annotated[int, Field(ge=0, le=7)] = 0
