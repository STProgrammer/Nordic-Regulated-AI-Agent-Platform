"""Public safe-contract tests for the closed Risk and Compliance workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.api.routes.workflows import workflow_run_data
from app.api.schemas.workflows import WorkflowStartRequest
from app.db.models.workflow import WorkflowRun
from app.services.workflows.risk import _draft_citation_labels
from pydantic import TypeAdapter, ValidationError


def test_risk_status_exposes_only_closed_final_assessment_fields() -> None:
    run = WorkflowRun(
        id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        started_by_user_id=uuid4(),
        workflow_name="risk_compliance",
        workflow_version="phase21-v1",
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        state_snapshot={
            "final_risk_level": "high",
            "reason_codes": ["pii_detected", "policy_conflict"],
            "approval_required": True,
            "safe_next_state": "human_review_required",
            "draft": "must never be exposed",
            "policy_rationale": "must never be exposed",
        },
    )

    data = workflow_run_data(run)

    assert data.workflow == "risk_compliance"
    assert data.risk_compliance is not None
    assert data.risk_compliance.final_risk_level is not None
    assert data.risk_compliance.final_risk_level.value == "high"
    assert data.risk_compliance.risk_reasons == ("pii_detected", "policy_conflict")
    assert data.risk_compliance.requires_approval is True
    assert "must never be exposed" not in data.model_dump_json()
    assert "policy_rationale" not in data.model_dump_json()


def test_risk_start_contract_rejects_client_policy_inputs() -> None:
    adapter: TypeAdapter[WorkflowStartRequest] = TypeAdapter(WorkflowStartRequest)
    accepted = adapter.validate_python({"workflow": "risk_compliance"})
    assert accepted.workflow == "risk_compliance"
    with pytest.raises(ValidationError):
        adapter.validate_python({"workflow": "risk_compliance", "risk_level": "low"})


def test_draft_prerequisite_reads_only_closed_citation_labels() -> None:
    assert _draft_citation_labels({"citation_labels": ["S1"], "content": "protected"}) == ("S1",)
    assert _draft_citation_labels({"content": "protected"}) == ()
