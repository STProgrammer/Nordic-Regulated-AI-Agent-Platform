"""Pure deterministic signal and preliminary-routing policy for Intake."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from agent_orchestrator.graphs.intake_types import (
    InjectionSignal,
    IntakeCaseType,
    IntakeDomain,
    IntakeLanguage,
    IntakePriority,
    PiiCategory,
    PreliminaryRiskLevel,
    SuggestedWorkflow,
)

_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
_NO_IDENTIFIER = re.compile(r"\b\d{6}[ -]?\d{5}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?47[ -]?)?\d{3}[ -]?\d{2}[ -]?\d{3}(?!\d)")
_OVERRIDE = re.compile(
    r"\b(?:ignore (?:all |previous )?instructions|disregard (?:all |previous )?instructions|"
    r"ignorer (?:alle |tidligere )?instruksjoner|system prompt)\b",
    re.IGNORECASE,
)


def detect_pii_signals(text: str) -> tuple[PiiCategory, ...]:
    """Return only categories for conservative bounded patterns, never matched text."""

    categories: list[PiiCategory] = []
    if _EMAIL.search(text):
        categories.append(PiiCategory.EMAIL)
    if _NO_IDENTIFIER.search(text):
        categories.append(PiiCategory.NORWEGIAN_NATIONAL_IDENTIFIER)
    if _PHONE.search(text):
        categories.append(PiiCategory.PHONE)
    return tuple(categories)


def detect_injection_signals(text: str) -> tuple[InjectionSignal, ...]:
    """Identify direct instruction override patterns without interpreting text as commands."""

    normalized = unicodedata.normalize("NFKC", text)
    return (InjectionSignal.INSTRUCTION_OVERRIDE,) if _OVERRIDE.search(normalized) else ()


@dataclass(frozen=True)
class PreliminaryRisk:
    level: PreliminaryRiskLevel
    reason_codes: tuple[str, ...]
    approval_required: bool


def estimate_preliminary_risk(
    *,
    priority: IntakePriority,
    detected_language: IntakeLanguage,
    low_confidence: bool,
    pii_detected: bool,
    prompt_injection_detected: bool,
) -> PreliminaryRisk:
    """Apply a transparent Intake-only risk table, not the later final risk policy."""

    reasons: list[str] = []
    if low_confidence:
        reasons.append("low_confidence")
    if detected_language is IntakeLanguage.UNKNOWN:
        reasons.append("language_unknown")
    if pii_detected:
        reasons.append("pii_detected")
    if prompt_injection_detected:
        reasons.append("prompt_injection_detected")
    if priority in {IntakePriority.HIGH, IntakePriority.URGENT}:
        reasons.append("priority_elevated")
    if prompt_injection_detected and priority is IntakePriority.URGENT:
        return PreliminaryRisk(PreliminaryRiskLevel.CRITICAL, tuple(reasons), True)
    if prompt_injection_detected or pii_detected or priority is IntakePriority.URGENT:
        return PreliminaryRisk(PreliminaryRiskLevel.HIGH, tuple(reasons), True)
    if (
        low_confidence
        or detected_language is IntakeLanguage.UNKNOWN
        or priority is IntakePriority.HIGH
    ):
        return PreliminaryRisk(PreliminaryRiskLevel.MEDIUM, tuple(reasons), False)
    return PreliminaryRisk(PreliminaryRiskLevel.LOW, tuple(reasons), False)


@dataclass(frozen=True)
class WorkflowRecommendation:
    workflow: SuggestedWorkflow
    reason_codes: tuple[str, ...]


def choose_suggested_workflow(
    *,
    case_type: IntakeCaseType,
    domain: IntakeDomain | None,
    low_confidence: bool,
    pii_detected: bool,
    prompt_injection_detected: bool,
) -> WorkflowRecommendation:
    """Recommend a later closed workflow without invoking or scheduling one."""

    if low_confidence or pii_detected or prompt_injection_detected or domain is None:
        return WorkflowRecommendation(SuggestedWorkflow.MANUAL_REVIEW, ("manual_review_required",))
    if case_type is IntakeCaseType.DOCUMENT_INTELLIGENCE:
        return WorkflowRecommendation(SuggestedWorkflow.EXTRACTION, ("document_intelligence",))
    if case_type is IntakeCaseType.POLICY_QUESTION:
        return WorkflowRecommendation(SuggestedWorkflow.EVIDENCE_THEN_DRAFT, ("policy_question",))
    if case_type in {IntakeCaseType.COMPLIANCE_REVIEW, IntakeCaseType.OPERATIONAL_INCIDENT}:
        return WorkflowRecommendation(SuggestedWorkflow.EVIDENCE, ("evidence_required",))
    return WorkflowRecommendation(SuggestedWorkflow.MANUAL_REVIEW, ("unclassified_intake",))
