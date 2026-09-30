from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.api.dependencies import (
    get_authentication_service,
    get_user_administration_service,
)
from app.core.config import AppSettings
from app.main import create_api_app
from app.services.auth.principal import Principal, RoleName
from app.services.common.pagination import Page
from app.services.errors import NotFoundError
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_session_handle_012345678901234567890123456789"


@dataclass
class _User:
    id: UUID
    email: str
    display_name: str
    preferred_language: str
    is_active: bool


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


class _AdministrationFake:
    def __init__(self, user: _User) -> None:
        self.user = user

    async def list_users(self, _principal: Principal, **_kwargs: object) -> Page[_User]:
        return Page(items=(self.user,), limit=25, offset=0, total=1)

    async def get_user(self, _principal: Principal, user_id: UUID) -> _User:
        if user_id != self.user.id:
            raise NotFoundError("User")
        return self.user

    async def role_names_for_user(self, _principal: Principal, _user_id: UUID) -> tuple[str, ...]:
        return (RoleName.ADMIN.value,)

    async def list_roles(self) -> tuple[SimpleNamespace, ...]:
        return (
            SimpleNamespace(
                id=uuid4(), name=RoleName.ADMIN.value, description="Synthetic administrator role"
            ),
        )

    async def add_user(self, _principal: Principal, _command: object) -> _User:
        return self.user

    async def update_user(self, _principal: Principal, user_id: UUID, _command: object) -> _User:
        return await self.get_user(_principal, user_id)

    async def replace_roles(
        self, _principal: Principal, user_id: UUID, _roles: tuple[RoleName, ...]
    ) -> tuple[object, ...]:
        await self.get_user(_principal, user_id)
        return ()


def _client(*roles: RoleName) -> tuple[TestClient, _User]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic Admin",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    user = _User(
        id=uuid4(),
        email="managed.user@demo.invalid",
        display_name="Managed User",
        preferred_language="nb",
        is_active=True,
    )
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_user_administration_service] = lambda: _AdministrationFake(user)
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, user


def test_user_management_requires_authenticated_admin() -> None:
    anonymous, _user = _client(RoleName.ADMIN)
    anonymous.cookies.clear()
    with anonymous:
        unauthenticated = anonymous.get("/api/users")
    assert unauthenticated.status_code == 401

    non_admin, _user = _client(RoleName.CASE_WORKER)
    with non_admin:
        forbidden = non_admin.get("/api/users")
    assert forbidden.status_code == 403


def test_admin_user_routes_are_tenant_scoped_and_safe() -> None:
    client, user = _client(RoleName.ADMIN)
    with client:
        listed = client.get("/api/users")
        detail = client.get(f"/api/users/{user.id}")
        foreign = client.get(f"/api/users/{uuid4()}")
        roles = client.get("/api/roles")
        invalid_submission = client.post(
            "/api/users",
            json={
                "email": "new.user@demo.invalid",
                "display_name": "New User",
                "preferred_language": "nb",
                "organization_id": str(uuid4()),
            },
        )

    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["email"] == user.email
    assert "password_hash" not in listed.text
    assert detail.status_code == 200
    assert foreign.status_code == 404
    assert roles.status_code == 200
    assert roles.json()["data"][0]["name"] == "Admin"
    assert invalid_submission.status_code == 422
