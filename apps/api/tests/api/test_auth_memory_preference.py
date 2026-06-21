"""Current-user-only language preference API contract."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from agent_orchestrator.graphs.drafting_types import OutputLanguage
from app.api.dependencies import get_authentication_service, get_controlled_memory_service
from app.core.config import AppSettings
from app.main import create_api_app
from app.services.auth.principal import Principal, RoleName
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_session_handle_012345678901234567890123456789"


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


class _MemoryFake:
    async def update_self_language(
        self, principal: Principal, *, language: OutputLanguage
    ) -> SimpleNamespace:
        return SimpleNamespace(id=principal.user_id, preferred_language=language.value)


def test_current_user_can_only_update_closed_language_preference() -> None:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic user",
        preferred_language="nb",
        roles=frozenset({RoleName.CASE_WORKER}),
    )
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_controlled_memory_service] = _MemoryFake
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    with client:
        changed = client.put("/api/auth/me/preferred-language", json={"preferred_language": "en"})
        forbidden_shape = client.put(
            "/api/auth/me/preferred-language",
            json={"preferred_language": "en", "user_id": str(uuid4())},
        )

    assert changed.status_code == 200
    assert changed.json()["data"]["user_id"] == str(principal.user_id)
    assert changed.json()["data"]["preferred_language"] == "en"
    assert forbidden_shape.status_code == 422
