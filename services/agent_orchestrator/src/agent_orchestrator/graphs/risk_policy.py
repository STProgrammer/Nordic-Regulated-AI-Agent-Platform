"""The closed, deterministic Phase-21 risk-routing matrix.

This is deliberately a small local policy boundary, not a generic policy engine.
Evidence defects always prevent a final assessment.  PII, sensitive-domain,
high-impact, policy-conflict, and prompt-injection signals force high risk;
low confidence forces a review-required medium result.  A future approval graph
owns the actual human decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_orchestrator.graphs.risk_types import (
    FinalRiskLevel,
    RiskReason,
    RiskSafeNextState,
    RiskSignals,
)


@dataclass(frozen=True)
class RiskPolicyDecision:
    """One deterministic policy outcome, without a rationale or score."""

    risk_level: FinalRiskLevel | None
    requires_approval: bool
    safe_next_state: RiskSafeNextState


def ordered_reasons(signals: RiskSignals) -> tuple[RiskReason, ...]:
    """Return each recognized reason once in architecture/policy order."""

    pairs = (
        (signals.pii_detected, RiskReason.PII_DETECTED),
        (signals.sensitive_domain, RiskReason.SENSITIVE_DOMAIN),
        (signals.weak_evidence, RiskReason.WEAK_EVIDENCE),
        (signals.contradictory_evidence, RiskReason.CONTRADICTORY_EVIDENCE),
        (signals.missing_required_source, RiskReason.MISSING_REQUIRED_SOURCE),
        (signals.low_confidence, RiskReason.LOW_CONFIDENCE),
        (signals.high_impact_action, RiskReason.HIGH_IMPACT_ACTION),
        (signals.policy_conflict, RiskReason.POLICY_CONFLICT),
        (signals.prompt_injection_detected, RiskReason.PROMPT_INJECTION_DETECTED),
    )
    return tuple(reason for present, reason in pairs if present)


def assess_risk(signals: RiskSignals) -> RiskPolicyDecision:
    """Apply the sole server-owned assessment matrix.

    Inadequate provenance never receives a final level.  Any final high result
    requires approval, and low-confidence output is routed to later human review
    even though its final level is medium.
    """

    if signals.weak_evidence or signals.contradictory_evidence or signals.missing_required_source:
        return RiskPolicyDecision(
            risk_level=None,
            requires_approval=False,
            safe_next_state=RiskSafeNextState.NEEDS_MORE_EVIDENCE,
        )
    if (
        signals.pii_detected
        or signals.sensitive_domain
        or signals.high_impact_action
        or signals.policy_conflict
        or signals.prompt_injection_detected
    ):
        return RiskPolicyDecision(
            risk_level=FinalRiskLevel.HIGH,
            requires_approval=True,
            safe_next_state=RiskSafeNextState.HUMAN_REVIEW_REQUIRED,
        )
    if signals.low_confidence:
        return RiskPolicyDecision(
            risk_level=FinalRiskLevel.MEDIUM,
            requires_approval=True,
            safe_next_state=RiskSafeNextState.HUMAN_REVIEW_REQUIRED,
        )
    return RiskPolicyDecision(
        risk_level=FinalRiskLevel.LOW,
        requires_approval=False,
        safe_next_state=RiskSafeNextState.ASSESSMENT_COMPLETE,
    )
