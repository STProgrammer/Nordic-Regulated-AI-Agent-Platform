"""Public contract coverage for Phase-23 audit and safe workflow-trace reads."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.api.dependencies import (
    get_audit_service,
    get_authentication_service,
    get_workflow_trace_service,
)
from app.api.schemas.workflows import WorkflowTraceData, WorkflowTraceHeaderData
from app.core.config import AppSettings
from app.db.models.audit import AuditEvent
from app.main import create_api_app
from app.services.auth.policy import (
    AuditAction,
    CaseAction,
    authorize_audit_action,
    authorize_case_action,
)
from app.services.auth.principal import Principal, RoleName
from app.services.common.pagination import Page, Pagination
from app.services.errors import NotFoundError
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_audit_session_012345678901234567890123456789"
_SENTINEL = "phase23-secret-sentinel-must-not-appear"


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


class _AuditFake:
    def __init__(self, event: AuditEvent) -> None:
        self.event = event
        self.filters: object | None = None

    async def list_for_principal(
        self, principal: Principal, *, pagination: Pagination, filters: object
    ) -> Page[AuditEvent]:
        authorize_audit_action(principal, AuditAction.READ)
        self.filters = filters
        return Page(items=(self.event,), limit=pagination.limit, offset=pagination.offset, total=1)

    async def list_for_case(
        self, principal: Principal, case_id: UUID, *, pagination: Pagination
    ) -> Page[AuditEvent]:
        authorize_case_action(principal, CaseAction.READ)
        if case_id != self.event.case_id:
            raise NotFoundError("Case")
        return Page(items=(self.event,), limit=pagination.limit, offset=pagination.offset, total=1)


class _TraceFake:
    def __init__(self, trace: WorkflowTraceData) -> None:
        self.trace = trace

    async def get_for_principal(
        self, principal: Principal, workflow_run_id: UUID
    ) -> WorkflowTraceData:
        authorize_case_action(principal, CaseAction.READ)
        if workflow_run_id != self.trace.header.workflow_run_id:
            raise NotFoundError("Workflow run")
        return self.trace


def _client(*roles: RoleName) -> tuple[TestClient, _AuditFake, WorkflowTraceData]:
    organization_id = uuid4()
    case_id = uuid4()
    run_id = uuid4()
    principal = Principal(
        user_id=uuid4(),
        organization_id=organization_id,
        display_name="Synthetic user",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    event = AuditEvent(
        id=uuid4(),
        organization_id=organization_id,
        actor_user_id=principal.user_id,
        case_id=case_id,
        resource_id=run_id,
        event_type="workflow.synthetic_completed",
        resource_type="workflow_run",
        inserted_at=datetime.now(UTC),
        event_data={
            "status": "completed",
            "nested": {"Authorization": _SENTINEL},
            "prompt_content": _SENTINEL,
        },
    )
    trace = WorkflowTraceData(
        header=WorkflowTraceHeaderData(
            workflow_run_id=run_id,
            workflow_name="synthetic",
            workflow_version="v1",
            case_id=case_id,
            status="completed",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=1,
            total_tokens=None,
            total_cost_estimate=None,
            final_error_code=None,
        ),
        final_state={"status": "completed"},
    )
    audit = _AuditFake(event)
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_audit_service] = lambda: audit
    app.dependency_overrides[get_workflow_trace_service] = lambda: _TraceFake(trace)
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, audit, trace


def test_audit_filters_are_tenant_derived_role_protected_and_sanitized() -> None:
    anonymous, _audit, _trace = _client(RoleName.ADMIN)
    anonymous.cookies.clear()
    with anonymous:
        assert anonymous.get("/api/audit/events").status_code == 401

    worker, _audit, trace = _client(RoleName.CASE_WORKER)
    with worker:
        assert worker.get("/api/audit/events").status_code == 403
        assert worker.get(f"/api/workflows/{trace.header.workflow_run_id}/trace").status_code == 200

    auditor, audit, _trace = _client(RoleName.READ_ONLY_AUDITOR)
    with auditor:
        response = auditor.get(
            "/api/audit/events",
            params={
                "case_id": str(audit.event.case_id),
                "event_type": audit.event.event_type,
                "resource_type": audit.event.resource_type,
                "inserted_after": "2026-01-01T00:00:00Z",
                "inserted_before": "2027-01-01T00:00:00Z",
                "organization_id": str(uuid4()),
            },
        )
    assert response.status_code == 200
    assert _SENTINEL not in response.text
    assert response.json()["data"]["items"][0]["metadata"] == {"status": "completed", "nested": {}}
    assert audit.filters is not None


def test_case_audit_and_workflow_trace_do_not_reveal_unknown_ids_or_unsafe_ranges() -> None:
    client, _audit, trace = _client(RoleName.MANAGER)
    with client:
        case_audit = client.get(f"/api/cases/{trace.header.case_id}/audit")
        foreign_case = client.get(f"/api/cases/{uuid4()}/audit")
        foreign_trace = client.get(f"/api/workflows/{uuid4()}/trace")
    auditor, _audit, _trace = _client(RoleName.ADMIN)
    with auditor:
        non_utc = auditor.get(
            "/api/audit/events", params={"inserted_after": "2026-01-01T00:00:00+01:00"}
        )
    assert case_audit.status_code == 200
    assert foreign_case.status_code == 404
    assert foreign_trace.status_code == 404
    assert non_utc.status_code == 400
