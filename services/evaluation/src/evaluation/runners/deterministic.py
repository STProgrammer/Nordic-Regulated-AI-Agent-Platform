"""Run checked-in fixtures through the same closed Intake and Risk policy seams."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol

from agent_orchestrator.graphs.intake_policy import choose_suggested_workflow
from agent_orchestrator.graphs.intake_types import IntakeDomain
from agent_orchestrator.graphs.risk_policy import assess_risk
from agent_orchestrator.graphs.risk_types import RiskSignals

from evaluation.contracts import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationDomain,
    ExpectedRiskOutcome,
    dataset_content_hash,
)
from evaluation.metrics import exact_boolean_score, score_expected_set


class EvaluationFailureCode(StrEnum):
    """Closed, content-free mismatch identifiers safe to persist and present."""

    RETRIEVAL_MISMATCH = "retrieval_mismatch"
    CITATION_MISMATCH = "citation_mismatch"
    CRITERION_MISMATCH = "criterion_mismatch"
    REFUSAL_MISMATCH = "refusal_mismatch"
    RISK_MISMATCH = "risk_mismatch"
    ROUTING_MISMATCH = "routing_mismatch"


@dataclass(frozen=True)
class EvaluationObservation:
    """Allowlisted fixture observations; logical keys are never database identifiers."""

    retrieved_source_keys: tuple[str, ...]
    citation_source_keys: tuple[str, ...]
    supported_answer_criterion_ids: tuple[str, ...]
    refused: bool
    risk_outcome: ExpectedRiskOutcome
    routing_outcome: str


class EvaluationScenarioExecutor(Protocol):
    """A narrow port that guarantees no model, embedding, network, or database access."""

    def execute(self, case: EvaluationCase) -> EvaluationObservation: ...


class DeterministicScenarioExecutor:
    """Adapt server-owned logical fixtures to existing pure policy functions."""

    def execute(self, case: EvaluationCase) -> EvaluationObservation:
        fixture = case.fixture
        refused = (
            fixture.weak_evidence
            or fixture.contradictory_evidence
            or fixture.missing_required_source
            or not fixture.retrieved_source_keys
        )
        risk = assess_risk(
            RiskSignals(
                pii_detected=fixture.pii_detected,
                sensitive_domain=fixture.sensitive_domain,
                weak_evidence=fixture.weak_evidence,
                contradictory_evidence=fixture.contradictory_evidence,
                missing_required_source=fixture.missing_required_source,
                low_confidence=fixture.low_confidence,
                high_impact_action=fixture.high_impact_action,
                policy_conflict=fixture.policy_conflict,
                prompt_injection_detected=fixture.prompt_injection_detected,
            )
        )
        routing = choose_suggested_workflow(
            case_type=fixture.case_type,
            domain=_intake_domain(case.domain),
            low_confidence=fixture.low_confidence,
            pii_detected=fixture.pii_detected,
            prompt_injection_detected=fixture.prompt_injection_detected,
        )
        risk_outcome = (
            ExpectedRiskOutcome.NEEDS_MORE_EVIDENCE
            if risk.risk_level is None
            else ExpectedRiskOutcome(risk.risk_level.value)
        )
        return EvaluationObservation(
            retrieved_source_keys=tuple(sorted(fixture.retrieved_source_keys)),
            citation_source_keys=() if refused else tuple(sorted(fixture.citation_source_keys)),
            supported_answer_criterion_ids=tuple(sorted(fixture.supported_answer_criterion_ids)),
            refused=refused,
            risk_outcome=risk_outcome,
            routing_outcome=routing.workflow.value,
        )


@dataclass(frozen=True)
class EvaluationCaseResult:
    """Safe per-case metric projection; no query, text, evidence, or provider data is retained."""

    case_key: str
    retrieval_score: float
    citation_score: float
    structural_faithfulness_score: float
    refusal_score: float
    risk_score: float
    routing_score: float
    passed: bool
    failure_codes: tuple[EvaluationFailureCode, ...]

    def as_safe_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationRunReport:
    """Stable compact report usable by the CLI and persistence adapters."""

    dataset_key: str
    dataset_version: str
    dataset_content_hash: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    passed: bool
    metric_pass_counts: dict[str, int]
    results: tuple[EvaluationCaseResult, ...]

    def safe_summary(self) -> dict[str, object]:
        return {
            "dataset_key": self.dataset_key,
            "dataset_version": self.dataset_version,
            "dataset_content_hash": self.dataset_content_hash,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "passed": self.passed,
            "metric_pass_counts": self.metric_pass_counts,
        }


def evaluate_dataset(
    dataset: EvaluationDataset, *, executor: EvaluationScenarioExecutor | None = None
) -> EvaluationRunReport:
    """Evaluate every case in deterministic key order and apply exact thresholds."""

    resolved_executor = executor or DeterministicScenarioExecutor()
    results = tuple(
        _evaluate_case(case, resolved_executor.execute(case))
        for case in sorted(dataset.cases, key=lambda item: item.case_key)
    )
    metric_pass_counts = {
        "retrieval": sum(result.retrieval_score == 1.0 for result in results),
        "citation": sum(result.citation_score == 1.0 for result in results),
        "structural_faithfulness": sum(
            result.structural_faithfulness_score == 1.0 for result in results
        ),
        "refusal": sum(result.refusal_score == 1.0 for result in results),
        "risk": sum(result.risk_score == 1.0 for result in results),
        "routing": sum(result.routing_score == 1.0 for result in results),
    }
    passed_cases = sum(result.passed for result in results)
    return EvaluationRunReport(
        dataset_key=dataset.dataset_key,
        dataset_version=dataset.version,
        dataset_content_hash=dataset_content_hash(dataset),
        total_cases=len(results),
        passed_cases=passed_cases,
        failed_cases=len(results) - passed_cases,
        passed=passed_cases == len(results),
        metric_pass_counts=metric_pass_counts,
        results=results,
    )


def _evaluate_case(
    case: EvaluationCase, observation: EvaluationObservation
) -> EvaluationCaseResult:
    retrieval = score_expected_set(case.expected_source_keys, observation.retrieved_source_keys)
    citations = score_expected_set(case.expected_citation_keys, observation.citation_source_keys)
    criteria = score_expected_set(
        case.expected_answer_criterion_ids, observation.supported_answer_criterion_ids
    )
    refusal_score, refusal_passed = exact_boolean_score(case.expect_refusal, observation.refused)
    risk_score, risk_passed = exact_boolean_score(
        case.expected_risk_outcome.value == observation.risk_outcome.value, True
    )
    routing_score, routing_passed = exact_boolean_score(
        case.expected_routing_outcome.value == observation.routing_outcome, True
    )
    failure_codes: list[EvaluationFailureCode] = []
    if not retrieval.passed:
        failure_codes.append(EvaluationFailureCode.RETRIEVAL_MISMATCH)
    if not citations.passed:
        failure_codes.append(EvaluationFailureCode.CITATION_MISMATCH)
    if not criteria.passed:
        failure_codes.append(EvaluationFailureCode.CRITERION_MISMATCH)
    if not refusal_passed:
        failure_codes.append(EvaluationFailureCode.REFUSAL_MISMATCH)
    if not risk_passed:
        failure_codes.append(EvaluationFailureCode.RISK_MISMATCH)
    if not routing_passed:
        failure_codes.append(EvaluationFailureCode.ROUTING_MISMATCH)
    return EvaluationCaseResult(
        case_key=case.case_key,
        retrieval_score=retrieval.average,
        citation_score=citations.average,
        structural_faithfulness_score=criteria.average,
        refusal_score=refusal_score,
        risk_score=risk_score,
        routing_score=routing_score,
        passed=not failure_codes,
        failure_codes=tuple(failure_codes),
    )


def _intake_domain(domain: EvaluationDomain) -> IntakeDomain:
    return {
        EvaluationDomain.PUBLIC_SECTOR: IntakeDomain.PUBLIC_SECTOR,
        EvaluationDomain.BANKING: IntakeDomain.BANKING_COMPLIANCE,
        EvaluationDomain.ENERGY: IntakeDomain.ENERGY_OPERATIONS,
        EvaluationDomain.INTERNAL_POLICY: IntakeDomain.INTERNAL_POLICY,
    }[domain]
