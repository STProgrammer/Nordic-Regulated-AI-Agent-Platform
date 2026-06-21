"""Offline contracts for the Phase-22 durable Human Approval Graph."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from agent_orchestrator.graphs.approval_graph import (
    APPROVAL_NODE_NAMES,
    ApprovalGraph,
    ApprovalGraphDependencies,
)
from agent_orchestrator.graphs.approval_types import ApprovalWorkflowState, ReviewerDecision
from agent_orchestrator.types import ModelUsage, RetryPolicy, RuntimeStatus, WorkflowContext
from pydantic import ValidationError


class MemoryPersistence:
    def __init__(self) -> None:
        self.node_names: list[str] = []
        self.snapshot: dict[str, object] | None = None
        self.paused_claimed = False

    async def claim_run(self, context: WorkflowContext) -> bool:
        return True

    async def claim_paused_run(self, context: WorkflowContext) -> bool:
        self.paused_claimed = True
        return True

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

    async def pause_run(
        self,
        context: WorkflowContext,
        *,
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
        workflow_name="human_approval",
        workflow_version="phase22-v1",
    )


def test_initial_review_interrupts_without_review_content_in_snapshot() -> None:
    async def run() -> MemoryPersistence:
        persistence = MemoryPersistence()
        interrupted: list[UUID] = []
        graph = ApprovalGraph(
            ApprovalGraphDependencies(
                persistence=persistence,
                prepare_review_packet=lambda _context: _approval_id(),
                mark_interrupted=lambda _context, approval_id: _interrupt(interrupted, approval_id),
                load_decision=lambda _context, _approval_id: _decision(None),
                resolve_decision=lambda _context, _approval_id, _decision_value: _resolve(),
                retry_policy=RetryPolicy(),
            )
        )
        context = _context()
        result = await graph.run_initial(context, ApprovalWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.WAITING_FOR_HUMAN_REVIEW
        assert interrupted == [result.state.approval_id]
        return persistence

    persistence = asyncio.run(run())
    assert persistence.node_names == list(APPROVAL_NODE_NAMES[:2])
    assert persistence.snapshot is not None
    assert persistence.snapshot["status"] == "waiting_for_human_review"
    assert "draft" not in str(persistence.snapshot).casefold()
    assert "comment" not in str(persistence.snapshot).casefold()


def test_resume_consumes_one_closed_persisted_decision() -> None:
    async def run() -> tuple[MemoryPersistence, list[ReviewerDecision]]:
        persistence = MemoryPersistence()
        resolved: list[ReviewerDecision] = []
        approval_id = uuid4()
        graph = ApprovalGraph(
            ApprovalGraphDependencies(
                persistence=persistence,
                prepare_review_packet=lambda _context: _approval_id(),
                mark_interrupted=lambda _context, _approval_id: _resolve(),
                load_decision=lambda _context, _approval_id: _decision(
                    ReviewerDecision.EDIT_AND_APPROVE
                ),
                resolve_decision=lambda _context, _approval_id, decision: _append(
                    resolved, decision
                ),
                retry_policy=RetryPolicy(),
            )
        )
        context = _context()
        result = await graph.run_resume(
            context,
            ApprovalWorkflowState(
                context=context,
                status=RuntimeStatus.WAITING_FOR_HUMAN_REVIEW,
                approval_id=approval_id,
            ),
        )
        assert result.outcome.status is RuntimeStatus.COMPLETED
        return persistence, resolved

    persistence, resolved = asyncio.run(run())
    assert persistence.paused_claimed is True
    assert persistence.node_names == list(APPROVAL_NODE_NAMES[2:])
    assert resolved == [ReviewerDecision.EDIT_AND_APPROVE]
    assert persistence.snapshot is not None
    assert persistence.snapshot["approval_decision"] == "edit_and_approve"


def test_approval_state_rejects_raw_review_text_and_unknown_actions() -> None:
    context = _context()
    with pytest.raises(ValidationError):
        ApprovalWorkflowState.model_validate({"context": context, "ai_draft": "private"})
    with pytest.raises(ValidationError):
        ApprovalWorkflowState.model_validate(
            {"context": context, "approval_decision": "approve_everything"}
        )


async def _approval_id() -> UUID:
    return uuid4()


async def _interrupt(interrupted: list[UUID], approval_id: UUID) -> None:
    interrupted.append(approval_id)


async def _decision(value: ReviewerDecision | None) -> ReviewerDecision | None:
    return value


async def _resolve() -> None:
    return None


async def _append(items: list[ReviewerDecision], decision: ReviewerDecision) -> None:
    items.append(decision)
