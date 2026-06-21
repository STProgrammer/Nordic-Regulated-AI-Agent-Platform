"""Focused closed-contract tests for the human approval API surface."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.api.routes.workflows import workflow_run_data
from app.api.schemas.approvals import (
    ApprovalCommentRequest,
    EditAndApproveRequest,
    MockHandoffRequest,
    ReassignApprovalRequest,
)
from app.db.models.workflow import WorkflowRun
from app.services.approvals.approved_output import MockHandoffTarget
from pydantic import ValidationError


def test_approval_requests_reject_unknown_or_blank_browser_fields() -> None:
    assert (
        ApprovalCommentRequest.model_validate(
            {"reviewer_comment": "  Synthetic reason  "}
        ).reviewer_comment
        == "Synthetic reason"
    )
    assert (
        EditAndApproveRequest.model_validate({"final_text": "  Synthetic final text  "}).final_text
        == "Synthetic final text"
    )
    assert ReassignApprovalRequest.model_validate({"assigned_user_id": uuid4()}).assigned_user_id
    assert MockHandoffRequest.model_validate({"target": "teams"}).target is MockHandoffTarget.TEAMS
    with pytest.raises(ValidationError):
        ApprovalCommentRequest.model_validate({"decision": "approve"})
    with pytest.raises(ValidationError):
        ApprovalCommentRequest.model_validate({"reviewer_comment": "   "})
    with pytest.raises(ValidationError):
        EditAndApproveRequest.model_validate({"final_text": " "})
    with pytest.raises(ValidationError):
        ReassignApprovalRequest.model_validate({"assigned_user_id": uuid4(), "risk": "high"})
    with pytest.raises(ValidationError):
        MockHandoffRequest.model_validate({"target": "webhook"})
    with pytest.raises(ValidationError):
        MockHandoffRequest.model_validate({"target": "email", "recipient": "unsafe@example"})


def test_safe_workflow_status_supports_human_review_without_packet_content() -> None:
    run = WorkflowRun(
        id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        started_by_user_id=uuid4(),
        workflow_name="human_approval",
        workflow_version="phase22-v1",
        status="waiting_for_human_review",
        started_at=datetime.now(UTC),
        state_snapshot={
            "approval_id": str(uuid4()),
            "approval_lifecycle": "pending",
            "ai_draft": "never public through workflow status",
            "provider": "never public through workflow status",
        },
    )

    data = workflow_run_data(run)

    assert data.workflow == "human_approval"
    assert data.status.value == "waiting_for_human_review"
    assert "ai_draft" not in data.model_dump_json()
    assert "provider" not in data.model_dump_json()
