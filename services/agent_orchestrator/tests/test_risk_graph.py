"""Offline contracts for the deterministic Phase-21 Risk and Compliance graph."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from agent_orchestrator.graphs.risk_graph import RISK_NODE_NAMES, RiskGraph, RiskGraphDependencies
from agent_orchestrator.graphs.risk_policy import assess_risk
from agent_orchestrator.graphs.risk_types import (
    FinalRiskLevel,
    RiskAssessmentResult,
    RiskReason,
    RiskSafeNextState,
    RiskSignals,
    RiskWorkflowState,
)
from agent_orchestrator.types import ModelUsage, RetryPolicy, RuntimeStatus, WorkflowContext
from pydantic import ValidationError


class MemoryPersistence:
    def __init__(self) -> None:
        self.node_names: list[str] = []
        self.snapshot: dict[str, object] | None = None

    async def claim_run(self, context: WorkflowContext) -> bool:
        return True

    async def claim_paused_run(self, context: WorkflowContext) -> bool:
        return True

    async def pause_run(
        self,
        context: WorkflowContext,
        *,
        state_snapshot: dict[str, object],
        duration_ms: int,
    ) -> None:
        self.snapshot = state_snapshot

    async def start_node(
        self,
        context: WorkflowContext,
        *,
        node_name: str,
        input_summary: dict[str, object],
        retry_count: int,
    ) -> UUID:
        self.node_names.append(node_name)
        return uuid4()

    async def finish_node(
        self,
        context: WorkflowContext,
        *,
        node_run_id: UUID,
        status: RuntimeStatus,
        output_summary: dict[str, object],
        duration_ms: int,
        retry_count: int,
        error_code: str | None = None,
    ) -> None:
        return None

    async def complete_run(
        self,
        context: WorkflowContext,
        *,
        status: RuntimeStatus,
        state_snapshot: dict[str, object],
        duration_ms: int,
    ) -> None:
        self.snapshot = state_snapshot

    async def fail_run(
        self,
        context: WorkflowContext,
        *,
        state_snapshot: dict[str, object],
        duration_ms: int,
        error_code: str,
    ) -> None:
        raise AssertionError(error_code)

    async def record_model_usage(self, context: WorkflowContext, usage: ModelUsage) -> None:
        return None


def _context() -> WorkflowContext:
    return WorkflowContext(
        workflow_run_id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        initiated_by_user_id=uuid4(),
        workflow_name="risk_compliance",
        workflow_version="phase21-v1",
    )


def _graph(
    persistence: MemoryPersistence,
    signals: RiskSignals,
    persisted: list[RiskAssessmentResult],
) -> RiskGraph:
    async def persist(
        _context: WorkflowContext,
        _state: RiskWorkflowState,
        result: RiskAssessmentResult,
    ) -> None:
        persisted.append(result)

    return RiskGraph(
        RiskGraphDependencies(
            signals=signals,
            persistence=persistence,
            persist_assessment=persist,
            retry_policy=RetryPolicy(),
        )
    )


def test_high_risk_requires_approval_and_persists_only_closed_state() -> None:
    async def run() -> tuple[MemoryPersistence, list[RiskAssessmentResult]]:
        persistence = MemoryPersistence()
        persisted: list[RiskAssessmentResult] = []
        graph = _graph(
            persistence,
            RiskSignals(pii_detected=True, prompt_injection_detected=True),
            persisted,
        )
        context = _context()
        result = await graph.run(context, RiskWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.COMPLETED
        return persistence, persisted

    persistence, persisted = asyncio.run(run())
    assert persistence.node_names == list(RISK_NODE_NAMES)
    assert persisted == [
        RiskAssessmentResult(
            risk_level=FinalRiskLevel.HIGH,
            risk_reasons=(RiskReason.PII_DETECTED, RiskReason.PROMPT_INJECTION_DETECTED),
            requires_approval=True,
            safe_next_state=RiskSafeNextState.HUMAN_REVIEW_REQUIRED,
        )
    ]
    assert persistence.snapshot is not None
    assert persistence.snapshot["final_risk_level"] == "high"
    assert persistence.snapshot["approval_required"] is True
    assert "draft" not in str(persistence.snapshot).casefold()


def test_evidence_defect_needs_more_evidence_without_assessment() -> None:
    async def run() -> tuple[MemoryPersistence, list[RiskAssessmentResult]]:
        persistence = MemoryPersistence()
        persisted: list[RiskAssessmentResult] = []
        graph = _graph(
            persistence,
            RiskSignals(contradictory_evidence=True, high_impact_action=True),
            persisted,
        )
        context = _context()
        result = await graph.run(context, RiskWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.NEEDS_MORE_EVIDENCE
        return persistence, persisted

    persistence, persisted = asyncio.run(run())
    assert persistence.node_names == list(RISK_NODE_NAMES)
    assert persisted == []
    assert persistence.snapshot is not None
    assert persistence.snapshot["status"] == "needs_more_evidence"
    assert persistence.snapshot["approval_required"] is False
    assert persistence.snapshot["reason_codes"] == [
        "contradictory_evidence",
        "high_impact_action",
    ]


@pytest.mark.parametrize(
    ("signals", "level", "approval", "next_state"),
    [
        (RiskSignals(), FinalRiskLevel.LOW, False, RiskSafeNextState.ASSESSMENT_COMPLETE),
        (
            RiskSignals(low_confidence=True),
            FinalRiskLevel.MEDIUM,
            True,
            RiskSafeNextState.HUMAN_REVIEW_REQUIRED,
        ),
        (
            RiskSignals(sensitive_domain=True),
            FinalRiskLevel.HIGH,
            True,
            RiskSafeNextState.HUMAN_REVIEW_REQUIRED,
        ),
        (
            RiskSignals(high_impact_action=True),
            FinalRiskLevel.HIGH,
            True,
            RiskSafeNextState.HUMAN_REVIEW_REQUIRED,
        ),
        (
            RiskSignals(policy_conflict=True),
            FinalRiskLevel.HIGH,
            True,
            RiskSafeNextState.HUMAN_REVIEW_REQUIRED,
        ),
        (RiskSignals(weak_evidence=True), None, False, RiskSafeNextState.NEEDS_MORE_EVIDENCE),
        (
            RiskSignals(missing_required_source=True),
            None,
            False,
            RiskSafeNextState.NEEDS_MORE_EVIDENCE,
        ),
    ],
)
def test_closed_policy_matrix(
    signals: RiskSignals,
    level: FinalRiskLevel | None,
    approval: bool,
    next_state: RiskSafeNextState,
) -> None:
    decision = assess_risk(signals)
    assert decision.risk_level is level
    assert decision.requires_approval is approval
    assert decision.safe_next_state is next_state


def test_risk_signals_reject_raw_content_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RiskSignals.model_validate({"pii_detected": True, "draft": "private text"})
