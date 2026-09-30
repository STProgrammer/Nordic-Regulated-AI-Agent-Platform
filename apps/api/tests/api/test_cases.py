from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.api.dependencies import get_authentication_service, get_case_service
from app.core.config import AppSettings
from app.db.repositories.case import CaseFilters
from app.main import create_api_app
from app.services.auth.policy import CaseAction, authorize_case_action
from app.services.auth.principal import Principal, RoleName
from app.services.cases.service import CasePatch
from app.services.common.pagination import Page
from app.services.errors import NotFoundError
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_session_handle_012345678901234567890123456789"


@dataclass
class _Case:
    id: UUID
    case_number: str
    title: str = "Synthetic case"
    description: str = "Synthetic description"
    language: str = "nb"
    domain: str = "public_sector"
    case_type: str | None = None
    priority: str = "normal"
    status: str = "new"
    risk_level: str | None = None
    assigned_user_id: UUID | None = None
    submitted_by_user_id: UUID | None = None
    due_date: date | None = date(2030, 1, 2)
    external_reference: str | None = "SYN-42"
    inserted_at: datetime = datetime(2030, 1, 1, tzinfo=UTC)
    updated_at: datetime = datetime(2030, 1, 1, tzinfo=UTC)
    archived_at: datetime | None = None


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


class _CasesFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal
        self.case = _Case(
            id=uuid4(),
            case_number="CASE-0123456789ABCDEF0123456789ABCDEF",
            submitted_by_user_id=principal.user_id,
        )
        self.last_filters: CaseFilters | None = None
        self.last_patch: CasePatch | None = None

    async def submit(self, principal: Principal, _command: object) -> _Case:
        authorize_case_action(principal, CaseAction.SUBMIT)
        return self.case

    async def list(self, principal: Principal, **kwargs: object) -> Page[_Case]:
        authorize_case_action(principal, CaseAction.READ)
        filters = kwargs["filters"]
        assert isinstance(filters, CaseFilters)
        self.last_filters = filters
        return Page(items=(self.case,), limit=25, offset=0, total=1)

    async def list_assignee_options(self, principal: Principal) -> tuple[tuple[UUID, str], ...]:
        authorize_case_action(principal, CaseAction.READ)
        return ((principal.user_id, "Synthetic Case User"),)

    async def get_required(self, principal: Principal, case_id: UUID) -> _Case:
        authorize_case_action(principal, CaseAction.READ)
        if case_id != self.case.id:
            raise NotFoundError("Case")
        return self.case

    async def patch(self, principal: Principal, case_id: UUID, command: CasePatch) -> _Case:
        authorize_case_action(principal, CaseAction.EDIT)
        if case_id != self.case.id:
            raise NotFoundError("Case")
        self.last_patch = command
        return self.case

    async def archive(self, principal: Principal, case_id: UUID) -> _Case:
        authorize_case_action(principal, CaseAction.ARCHIVE)
        if case_id != self.case.id:
            raise NotFoundError("Case")
        self.case.status = "archived"
        self.case.archived_at = datetime(2030, 1, 3, tzinfo=UTC)
        return self.case


def _client(*roles: RoleName) -> tuple[TestClient, _CasesFake]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic Case User",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    cases = _CasesFake(principal)
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_case_service] = lambda: cases
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, cases


def test_case_routes_require_a_session_and_backend_role() -> None:
    anonymous, _cases = _client(RoleName.CASE_WORKER)
    anonymous.cookies.clear()
    with anonymous:
        unauthenticated = anonymous.get("/api/cases")
    assert unauthenticated.status_code == 401

    auditor, _cases = _client(RoleName.READ_ONLY_AUDITOR)
    with auditor:
        forbidden = auditor.post("/api/cases", json=_submission_payload())
    assert forbidden.status_code == 403


def test_case_submission_uses_a_safe_server_owned_view() -> None:
    client, _cases = _client(RoleName.CASE_WORKER)
    with client:
        submission = client.post("/api/cases", json=_submission_payload())
        forbidden_field = client.post(
            "/api/cases",
            json={**_submission_payload(), "organization_id": str(uuid4())},
        )

    assert submission.status_code == 201
    data = submission.json()["data"]
    assert data["case_number"].startswith("CASE-")
    assert data["status"] == "new"
    assert data["due_date"] == "2030-01-02"
    assert "organization_id" not in data
    assert forbidden_field.status_code == 422


def test_case_list_and_mutation_contracts_are_bounded_and_tenant_safe() -> None:
    client, cases = _client(RoleName.CASE_WORKER)
    with client:
        listed = client.get(
            "/api/cases",
            params={"status": "new", "domain": "public_sector", "q": "case"},
        )
        detail = client.get(f"/api/cases/{cases.case.id}")
        foreign = client.get(f"/api/cases/{uuid4()}")
        cleared = client.patch(
            f"/api/cases/{cases.case.id}",
            json={"assigned_user_id": None, "due_date": None, "external_reference": None},
        )
        empty_patch = client.patch(f"/api/cases/{cases.case.id}", json={})
        archived = client.post(f"/api/cases/{cases.case.id}/archive")

    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1
    assert cases.last_filters is not None
    assert cases.last_filters.search_text == "case"
    assert detail.status_code == 200
    assert foreign.status_code == 404
    assert cleared.status_code == 200
    assert cases.last_patch is not None
    assert cases.last_patch.assigned_user_id is None
    assert empty_patch.status_code == 422
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    assert archived.json()["data"]["archived_at"] == "2030-01-03T00:00:00Z"


def test_case_assignee_choices_are_case_read_protected_and_minimal() -> None:
    client, _cases = _client(RoleName.READ_ONLY_AUDITOR)
    with client:
        response = client.get("/api/cases/assignees")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "items": [
            {
                "user_id": str(_cases.principal.user_id),
                "display_name": "Synthetic Case User",
            }
        ]
    }
    assert "email" not in response.text
    assert "roles" not in response.text


def _submission_payload() -> dict[str, str]:
    return {
        "title": "  Synthetic submission  ",
        "description": "  A safe synthetic description.  ",
        "domain": "public_sector",
        "priority": "normal",
        "language": "nb",
        "due_date": "2030-01-02",
        "external_reference": "SYN-42",
    }
