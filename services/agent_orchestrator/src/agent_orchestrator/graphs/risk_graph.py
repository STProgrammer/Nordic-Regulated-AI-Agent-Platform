"""The fixed seven-node Risk and Compliance LangGraph."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.graphs.risk_policy import assess_risk, ordered_reasons
from agent_orchestrator.graphs.risk_types import (
    RiskAssessmentResult,
    RiskSignals,
    RiskWorkflowState,
)
from agent_orchestrator.graphs.runtime import GraphNode, GraphRunResult, GraphRuntime
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.types import RetryPolicy, RuntimeStatus, WorkflowContext

PersistRiskAssessment = Callable[
    [WorkflowContext, RiskWorkflowState, RiskAssessmentResult], Awaitable[None]
]


@dataclass(frozen=True)
class RiskGraphDependencies:
    """Server-built graph dependencies; no provider or browser input exists."""

    signals: RiskSignals
    persistence: WorkflowPersistence
    persist_assessment: PersistRiskAssessment
    retry_policy: RetryPolicy


RISK_NODE_NAMES: tuple[str, ...] = (
    "check_pii_policy",
    "check_weak_evidence",
    "check_high_impact_action",
    "check_policy_conflict",
    "check_prompt_injection_result",
    "assign_final_risk",
    "decide_approval_requirement",
)


class RiskGraph:
    """Evaluate only persisted closed signals in the architecture-defined order."""

    def __init__(self, dependencies: RiskGraphDependencies) -> None:
        self._dependencies = dependencies
        self._runtime = GraphRuntime[RiskWorkflowState](
            state_model=RiskWorkflowState,
            persistence=dependencies.persistence,
            retry_policy=dependencies.retry_policy,
        )

    async def run(
        self, context: WorkflowContext, initial_state: RiskWorkflowState
    ) -> GraphRunResult[RiskWorkflowState]:
        return await self._runtime.run(context, initial_state, self._nodes())

    def _nodes(self) -> tuple[GraphNode[RiskWorkflowState], ...]:
        return (
            GraphNode("check_pii_policy", self._check_pii_policy),
            GraphNode("check_weak_evidence", self._check_weak_evidence),
            GraphNode("check_high_impact_action", self._check_high_impact_action),
            GraphNode("check_policy_conflict", self._check_policy_conflict),
            GraphNode("check_prompt_injection_result", self._check_prompt_injection_result),
            GraphNode("assign_final_risk", self._assign_final_risk),
            GraphNode("decide_approval_requirement", self._decide_approval_requirement),
        )

    async def _check_pii_policy(self, state: RiskWorkflowState) -> dict[str, object]:
        signals = self._dependencies.signals
        return self._update(
            state,
            pii_detected=signals.pii_detected,
            sensitive_domain=signals.sensitive_domain,
        )

    async def _check_weak_evidence(self, state: RiskWorkflowState) -> dict[str, object]:
        signals = self._dependencies.signals
        return self._update(
            state,
            weak_evidence=signals.weak_evidence,
            contradictory_evidence=signals.contradictory_evidence,
            missing_required_source=signals.missing_required_source,
        )

    async def _check_high_impact_action(self, state: RiskWorkflowState) -> dict[str, object]:
        return self._update(state, high_impact_action=self._dependencies.signals.high_impact_action)

    async def _check_policy_conflict(self, state: RiskWorkflowState) -> dict[str, object]:
        return self._update(state, policy_conflict=self._dependencies.signals.policy_conflict)

    async def _check_prompt_injection_result(self, state: RiskWorkflowState) -> dict[str, object]:
        signals = self._dependencies.signals
        return self._update(
            state,
            low_confidence=signals.low_confidence,
            prompt_injection_detected=signals.prompt_injection_detected,
        )

    async def _assign_final_risk(self, state: RiskWorkflowState) -> dict[str, object]:
        signals = self._state_signals(state)
        decision = assess_risk(signals)
        updates: dict[str, object] = {
            "reason_codes": ordered_reasons(signals),
            "safe_next_state": decision.safe_next_state,
            "node_count": state.node_count + 1,
        }
        if decision.risk_level is None:
            updates.update(
                {
                    "status": RuntimeStatus.NEEDS_MORE_EVIDENCE,
                    "final_risk_level": None,
                    "approval_required": False,
                }
            )
        else:
            updates["final_risk_level"] = decision.risk_level
        return updates

    async def _decide_approval_requirement(self, state: RiskWorkflowState) -> dict[str, object]:
        if state.status is RuntimeStatus.NEEDS_MORE_EVIDENCE:
            return {"node_count": state.node_count + 1, "approval_required": False}
        signals = self._state_signals(state)
        decision = assess_risk(signals)
        if (
            decision.risk_level is None
            or state.final_risk_level is None
            or state.safe_next_state is None
        ):
            raise ControlledWorkflowError("invalid_risk_policy_state")
        final_state = state.model_copy(
            update={
                "approval_required": decision.requires_approval,
                "node_count": state.node_count + 1,
            }
        )
        result = RiskAssessmentResult(
            risk_level=state.final_risk_level,
            risk_reasons=state.reason_codes,
            requires_approval=decision.requires_approval,
            safe_next_state=state.safe_next_state,
        )
        await self._dependencies.persist_assessment(state.context, final_state, result)
        return {
            "approval_required": decision.requires_approval,
            "node_count": final_state.node_count,
        }

    @staticmethod
    def _state_signals(state: RiskWorkflowState) -> RiskSignals:
        return RiskSignals(
            pii_detected=state.pii_detected,
            sensitive_domain=state.sensitive_domain,
            weak_evidence=state.weak_evidence,
            contradictory_evidence=state.contradictory_evidence,
            missing_required_source=state.missing_required_source,
            low_confidence=state.low_confidence,
            high_impact_action=state.high_impact_action,
            policy_conflict=state.policy_conflict,
            prompt_injection_detected=state.prompt_injection_detected,
        )

    @staticmethod
    def _update(state: RiskWorkflowState, **updates: bool) -> dict[str, object]:
        # Keep reason codes in fixed order while removing any duplicate safe signal.
        candidate = state.model_copy(update=updates)
        return {
            **updates,
            "reason_codes": ordered_reasons(RiskGraph._state_signals(candidate)),
            "node_count": state.node_count + 1,
        }
