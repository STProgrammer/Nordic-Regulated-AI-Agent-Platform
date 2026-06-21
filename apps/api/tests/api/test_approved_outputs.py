"""Cookie/RBAC and attachment-contract coverage for approved-output actions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.api.dependencies import get_approved_output_service, get_authentication_service
from app.core.config import AppSettings
from app.main import create_api_app
from app.services.approvals.approved_output import (
    ApprovedOutputFormat,
    MockHandoffRecord,
    MockHandoffTarget,
    RenderedApprovedOutput,
)
from app.services.auth.policy import ensure_roles
from app.services.auth.principal import Principal, RoleName
from app.services.errors import NotFoundError
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_approved_output_session_012345678901234567890123"


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


@dataclass
class _ApprovedOutputFake:
    approval_id: UUID

    async def export(
        self, principal: Principal, approval_id: UUID, *, export_format: ApprovedOutputFormat
    ) -> RenderedApprovedOutput:
        ensure_roles(principal, RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER)
        if approval_id != self.approval_id:
            raise NotFoundError("Approval")
        names = {
            ApprovedOutputFormat.JSON: (
                "approved-output.json",
                "application/json",
                b'{"safe":true}\n',
            ),
            ApprovedOutputFormat.CSV: (
                "approved-output.csv",
                "text/csv; charset=utf-8",
                b"field_name\n",
            ),
            ApprovedOutputFormat.MARKDOWN: (
                "approved-output.md",
                "text/markdown; charset=utf-8",
                b"# Safe\n",
            ),
            ApprovedOutputFormat.PDF: ("approved-output.pdf", "application/pdf", b"%PDF-synthetic"),
        }
        filename, media_type, content = names[export_format]
        return RenderedApprovedOutput(content=content, filename=filename, media_type=media_type)

    async def record_mock_handoff(
        self, principal: Principal, approval_id: UUID, *, target: MockHandoffTarget
    ) -> MockHandoffRecord:
        ensure_roles(principal, RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER)
        if approval_id != self.approval_id:
            raise NotFoundError("Approval")
        return MockHandoffRecord(
            approval_id=approval_id,
            target=target,
            status="recorded",
            mode="mock",
        )


def _client(*roles: RoleName) -> tuple[TestClient, _ApprovedOutputFake]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic reviewer",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    service = _ApprovedOutputFake(approval_id=uuid4())
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_approved_output_service] = lambda: service
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, service


def test_approved_output_routes_require_reviewer_role_and_have_fixed_attachments() -> None:
    denied, denied_service = _client(RoleName.CASE_WORKER)
    with denied:
        assert (
            denied.post(f"/api/approvals/{denied_service.approval_id}/exports/json").status_code
            == 403
        )
        assert (
            denied.post(
                f"/api/approvals/{denied_service.approval_id}/mock-handoffs",
                json={"target": "teams"},
            ).status_code
            == 403
        )

    client, service = _client(RoleName.COMPLIANCE_REVIEWER)
    with client:
        responses = {
            export_format: client.post(
                f"/api/approvals/{service.approval_id}/exports/{export_format}"
            )
            for export_format in ("json", "csv", "markdown", "pdf")
        }
        handoff = client.post(
            f"/api/approvals/{service.approval_id}/mock-handoffs", json={"target": "teams"}
        )
        malformed_target = client.post(
            f"/api/approvals/{service.approval_id}/mock-handoffs", json={"target": "webhook"}
        )
        extra_handoff = client.post(
            f"/api/approvals/{service.approval_id}/mock-handoffs",
            json={"target": "email", "recipient": "unsafe@example"},
        )
        missing = client.post(f"/api/approvals/{uuid4()}/exports/json")

    assert (
        responses["json"].headers["content-disposition"]
        == 'attachment; filename="approved-output.json"'
    )
    assert responses["json"].headers["content-type"] == "application/json"
    assert (
        responses["csv"].headers["content-disposition"]
        == 'attachment; filename="approved-output.csv"'
    )
    assert responses["csv"].headers["content-type"].startswith("text/csv")
    assert (
        responses["markdown"].headers["content-disposition"]
        == 'attachment; filename="approved-output.md"'
    )
    assert responses["markdown"].headers["content-type"].startswith("text/markdown")
    assert (
        responses["pdf"].headers["content-disposition"]
        == 'attachment; filename="approved-output.pdf"'
    )
    assert responses["pdf"].headers["content-type"] == "application/pdf"
    assert handoff.status_code == 200
    assert handoff.json()["data"] == {
        "approval_id": str(service.approval_id),
        "target": "teams",
        "status": "recorded",
        "mode": "mock",
    }
    assert "content" not in handoff.text
    assert malformed_target.status_code == 422
    assert extra_handoff.status_code == 422
    assert missing.status_code == 404
