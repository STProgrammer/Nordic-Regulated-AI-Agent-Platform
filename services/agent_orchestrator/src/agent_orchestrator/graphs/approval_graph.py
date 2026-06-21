"""Typed Human Approval Graph with an explicit persisted interruption and resume path."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.graphs.approval_types import (
    ApprovalLifecycle,
    ApprovalWorkflowState,
    ReviewerDecision,
)
from agent_orchestrator.graphs.runtime import GraphNode, GraphRunResult, GraphRuntime
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.types import RetryPolicy, RuntimeStatus, WorkflowContext

PrepareReviewPacket = Callable[[WorkflowContext], Awaitable[UUID]]
MarkInterrupted = Callable[[WorkflowContext, UUID], Awaitable[None]]
LoadDecision = Callable[[WorkflowContext, UUID], Awaitable[ReviewerDecision | None]]
ResolveDecision = Callable[[WorkflowContext, UUID, ReviewerDecision], Awaitable[None]]


APPROVAL_NODE_NAMES: tuple[str, ...] = (
    "prepare_review_packet",
    "interrupt_for_human_review",
    "handle_approval",
    "handle_rejection",
    "handle_edit",
    "handle_more_evidence_request",
    "resume_workflow",
)


@dataclass(frozen=True)
class ApprovalGraphDependencies:
    """Server-built persistence callbacks; they never accept browser or model content."""

    persistence: WorkflowPersistence
    prepare_review_packet: PrepareReviewPacket
    mark_interrupted: MarkInterrupted
    load_decision: LoadDecision
    resolve_decision: ResolveDecision
    retry_policy: RetryPolicy


class ApprovalGraph:
    """Pause after packet preparation, then resume once from one persisted decision."""

    def __init__(self, dependencies: ApprovalGraphDependencies) -> None:
        self._dependencies = dependencies
        self._runtime = GraphRuntime[ApprovalWorkflowState](
            state_model=ApprovalWorkflowState,
            persistence=dependencies.persistence,
            retry_policy=dependencies.retry_policy,
        )

    async def run_initial(
        self, context: WorkflowContext, initial_state: ApprovalWorkflowState
    ) -> GraphRunResult[ApprovalWorkflowState]:
        """Prepare one packet and durably interrupt before any reviewer decision exists."""

        return await self._runtime.run(context, initial_state, self._initial_nodes())

    async def run_resume(
        self, context: WorkflowContext, paused_state: ApprovalWorkflowState
    ) -> GraphRunResult[ApprovalWorkflowState]:
        """Claim one persisted interruption and apply only its already-validated decision."""

        return await self._runtime.run(
            context,
            paused_state,
            self._resume_nodes(),
            claim_mode="paused",
        )

    def _initial_nodes(self) -> tuple[GraphNode[ApprovalWorkflowState], ...]:
        return (
            GraphNode("prepare_review_packet", self.prepare_review_packet),
            GraphNode("interrupt_for_human_review", self.interrupt_for_human_review),
        )

    def _resume_nodes(self) -> tuple[GraphNode[ApprovalWorkflowState], ...]:
        return (
            GraphNode("handle_approval", self.handle_approval),
            GraphNode("handle_rejection", self.handle_rejection),
            GraphNode("handle_edit", self.handle_edit),
            GraphNode("handle_more_evidence_request", self.handle_more_evidence_request),
            GraphNode("resume_workflow", self.resume_workflow),
        )

    async def prepare_review_packet(self, state: ApprovalWorkflowState) -> dict[str, object]:
        approval_id = await self._dependencies.prepare_review_packet(state.context)
        return {
            "approval_id": approval_id,
            "approval_lifecycle": ApprovalLifecycle.PENDING,
            "approval_required": True,
            "node_count": state.node_count + 1,
        }

    async def interrupt_for_human_review(self, state: ApprovalWorkflowState) -> dict[str, object]:
        if state.approval_id is None:
            raise ControlledWorkflowError("approval_packet_unavailable")
        await self._dependencies.mark_interrupted(state.context, state.approval_id)
        return {
            "status": RuntimeStatus.WAITING_FOR_HUMAN_REVIEW,
            "approval_required": True,
            "node_count": state.node_count + 1,
        }

    async def handle_approval(self, state: ApprovalWorkflowState) -> dict[str, object]:
        return await self._match_decision(state, ReviewerDecision.APPROVE)

    async def handle_rejection(self, state: ApprovalWorkflowState) -> dict[str, object]:
        return await self._match_decision(state, ReviewerDecision.REJECT)

    async def handle_edit(self, state: ApprovalWorkflowState) -> dict[str, object]:
        return await self._match_decision(state, ReviewerDecision.EDIT_AND_APPROVE)

    async def handle_more_evidence_request(self, state: ApprovalWorkflowState) -> dict[str, object]:
        return await self._match_decision(state, ReviewerDecision.REQUEST_MORE_EVIDENCE)

    async def resume_workflow(self, state: ApprovalWorkflowState) -> dict[str, object]:
        if state.approval_id is None or state.approval_decision is None:
            raise ControlledWorkflowError("approval_decision_unavailable")
        await self._dependencies.resolve_decision(
            state.context, state.approval_id, state.approval_decision
        )
        lifecycle = (
            ApprovalLifecycle.APPROVED
            if state.approval_decision
            in (ReviewerDecision.APPROVE, ReviewerDecision.EDIT_AND_APPROVE)
            else ApprovalLifecycle.REJECTED
            if state.approval_decision is ReviewerDecision.REJECT
            else ApprovalLifecycle.NEEDS_MORE_EVIDENCE
        )
        return {
            "status": RuntimeStatus.COMPLETED,
            "approval_lifecycle": lifecycle,
            "node_count": state.node_count + 1,
        }

    async def _match_decision(
        self, state: ApprovalWorkflowState, expected: ReviewerDecision
    ) -> dict[str, object]:
        if state.approval_id is None:
            raise ControlledWorkflowError("approval_packet_unavailable")
        decision = await self._dependencies.load_decision(state.context, state.approval_id)
        if decision is None:
            raise ControlledWorkflowError("approval_decision_unavailable")
        updates: dict[str, object] = {"node_count": state.node_count + 1}
        if decision is expected:
            updates["approval_decision"] = decision
        return updates
