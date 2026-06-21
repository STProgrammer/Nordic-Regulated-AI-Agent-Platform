"""Closed state and decision types for the durable human approval graph."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from agent_orchestrator.state.case_state import CaseWorkflowState


class ApprovalLifecycle(StrEnum):
    """Persisted lifecycle labels safe for status projections and snapshots."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class ReviewerDecision(StrEnum):
    """The only server-validated human review outcomes."""

    APPROVE = "approve"
    EDIT_AND_APPROVE = "edit_and_approve"
    REJECT = "reject"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"


class ApprovalWorkflowState(CaseWorkflowState):
    """Identifier-only graph state; protected review content never enters this model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_id: UUID | None = None
    approval_lifecycle: ApprovalLifecycle = ApprovalLifecycle.PENDING
    approval_decision: ReviewerDecision | None = None
    node_count: Annotated[int, Field(ge=0, le=7)] = 0
