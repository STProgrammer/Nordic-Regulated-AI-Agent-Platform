"""Cookie/RBAC and strict-contract coverage for the Admin memory boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from agent_orchestrator.memory.policy import MemoryScope, MemoryType, validate_memory_payload
from app.api.dependencies import get_authentication_service, get_controlled_memory_service
from app.core.config import AppSettings
from app.db.models.memory import MemoryEntry
from app.main import create_api_app
from app.services.auth.principal import Principal, RoleName
from app.services.errors import NotFoundError
from app.services.memory.service import MemoryEntryInput, MemoryEntryRevision
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_session_handle_012345678901234567890123456789"


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


@dataclass
class _MemoryFake:
    organization_id: UUID
    enabled: bool = False
    entry: MemoryEntry | None = None

    async def enabled_for_organization(self, organization_id: UUID) -> bool:
        assert organization_id == self.organization_id
        return self.enabled

    async def set_enabled(self, _principal: Principal, *, enabled: bool) -> bool:
        self.enabled = enabled
        return enabled

    async def list_organization_entries(
        self, _principal: Principal, *, include_archived: bool
    ) -> tuple[MemoryEntry, ...]:
        if self.entry is None or (self.entry.archived_at is not None and not include_archived):
            return ()
        return (self.entry,)

    async def add_organization_entry(
        self, principal: Principal, command: MemoryEntryInput
    ) -> MemoryEntry:
        payload = validate_memory_payload(
            memory_scope=MemoryScope.ORGANIZATION,
            memory_type=command.memory_type,
            payload=command.content,
        )
        now = datetime.now(UTC)
        self.entry = MemoryEntry(
            id=uuid4(),
            organization_id=principal.organization_id,
            user_id=None,
            memory_scope="organization",
            memory_type=command.memory_type.value,
            content=payload.model_dump(mode="json"),
            source="admin_approved",
            store_key=str(uuid4()),
            natural_key="synthetic",
            is_active=True,
            inserted_at=now,
            updated_at=now,
        )
        return self.entry

    async def revise_organization_entry(
        self, principal: Principal, entry_id: UUID, command: MemoryEntryRevision
    ) -> MemoryEntry:
        if (
            self.entry is None
            or entry_id != self.entry.id
            or principal.organization_id != self.organization_id
        ):
            raise NotFoundError("Memory entry")
        payload = validate_memory_payload(
            memory_scope=MemoryScope.ORGANIZATION,
            memory_type=MemoryType(self.entry.memory_type),
            payload=command.content,
        )
        self.entry.content = payload.model_dump(mode="json")
        return self.entry

    async def archive_organization_entry(self, principal: Principal, entry_id: UUID) -> MemoryEntry:
        if (
            self.entry is None
            or entry_id != self.entry.id
            or principal.organization_id != self.organization_id
        ):
            raise NotFoundError("Memory entry")
        self.entry.is_active = False
        self.entry.archived_at = datetime.now(UTC)
        return self.entry

    async def record_rejected_write(self, _principal: Principal, **_kwargs: object) -> None:
        return None


def _client(*roles: RoleName) -> tuple[TestClient, _MemoryFake]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic administrator",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    memory = _MemoryFake(organization_id=principal.organization_id)
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_controlled_memory_service] = lambda: memory
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, memory


def test_memory_admin_operations_are_role_protected_and_strict() -> None:
    denied, _memory = _client(RoleName.CASE_WORKER)
    with denied:
        assert denied.get("/api/admin/memory/settings").status_code == 403

    client, _memory = _client(RoleName.ADMIN)
    with client:
        initial = client.get("/api/admin/memory/settings")
        enabled = client.put("/api/admin/memory/settings", json={"enabled": True})
        response = client.post(
            "/api/admin/memory/entries",
            json={
                "memory_type": "approved_terminology",
                "content": {
                    "locale": "nb",
                    "source_term": "vedtak",
                    "preferred_term": "avgjørelse",
                },
            },
        )
        invalid = client.post(
            "/api/admin/memory/entries",
            json={
                "memory_type": "approved_terminology",
                "content": {
                    "locale": "nb",
                    "source_term": "term",
                    "preferred_term": "person@demo.invalid",
                },
            },
        )
        extra = client.put(
            "/api/admin/memory/settings", json={"enabled": True, "organization_id": str(uuid4())}
        )

    assert initial.json()["data"] == {"enabled": False}
    assert enabled.json()["data"] == {"enabled": True}
    assert response.status_code == 201
    assert response.json()["data"]["memory_scope"] == "organization"
    assert "store_key" not in response.text
    assert invalid.status_code == 422
    assert extra.status_code == 422
