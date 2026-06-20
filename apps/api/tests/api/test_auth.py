from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.api.dependencies import get_authentication_service, get_login_rate_limiter
from app.core.config import AppSettings
from app.core.rate_limit import RateLimitDecision
from app.core.session_store import AuthStateUnavailableError
from app.main import create_api_app
from app.services.auth.principal import Principal, RoleName
from app.services.auth.service import LoginRejected, LoginResult, LoginSucceeded
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_session_handle_012345678901234567890123456789"


@dataclass
class _AuthenticationFake:
    principal: Principal
    login_result: LoginResult
    logout_calls: int = 0

    async def login(self, _command: object) -> LoginResult:
        return self.login_result

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None

    async def logout(self, _principal: Principal, _session_id: str) -> None:
        self.logout_calls += 1


class _AllowingLimiter:
    async def check(self, _email: str, _origin: str) -> RateLimitDecision:
        return RateLimitDecision(allowed=True)


class _BlockingLimiter:
    async def check(self, _email: str, _origin: str) -> RateLimitDecision:
        return RateLimitDecision(allowed=False, retry_after_seconds=42)


class _UnavailableLimiter:
    async def check(self, _email: str, _origin: str) -> RateLimitDecision:
        raise AuthStateUnavailableError("synthetic test outage")


def _principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic User",
        preferred_language="nb",
        roles=frozenset({RoleName.ADMIN}),
    )


def _client(
    result: LoginResult | None = None,
    *,
    limiter: object | None = None,
) -> tuple[TestClient, _AuthenticationFake]:
    principal = _principal()
    authentication = _AuthenticationFake(
        principal=principal,
        login_result=result
        if result is not None
        else LoginSucceeded(principal=principal, session_id=_SESSION_ID),
    )
    app = create_api_app(AppSettings(environment="test", session_ttl_seconds=600))
    app.dependency_overrides[get_authentication_service] = lambda: authentication
    app.dependency_overrides[get_login_rate_limiter] = lambda: (
        limiter if limiter is not None else _AllowingLimiter()
    )
    return TestClient(app), authentication


def test_login_sets_http_only_opaque_cookie_and_me_requires_it() -> None:
    client, _authentication = _client()
    with client:
        login = client.post(
            "/api/auth/login",
            json={"email": "USER@demo.invalid", "password": "synthetic password"},
        )
        me = client.get("/api/auth/me")

    assert login.status_code == 200
    assert _SESSION_ID not in login.text
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie
    assert me.status_code == 200
    assert me.json()["data"]["roles"] == ["Admin"]


def test_invalid_login_is_generic_and_does_not_set_a_cookie() -> None:
    client, _authentication = _client(LoginRejected())
    with client:
        response = client.post(
            "/api/auth/login",
            json={"email": "unknown@demo.invalid", "password": "anything"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "invalid_credentials",
        "message": "Invalid email or password.",
        "request_id": response.headers["X-Request-ID"],
        "details": None,
    }
    assert "set-cookie" not in response.headers


def test_me_rejects_missing_or_forged_session() -> None:
    client, _authentication = _client()
    with client:
        missing = client.get("/api/auth/me")
        client.cookies.set("nordic_session", "forged-session")
        forged = client.get("/api/auth/me")

    assert missing.status_code == 401
    assert forged.status_code == 401


def test_logout_clears_cookie_and_invalidates_server_session() -> None:
    client, authentication = _client()
    with client:
        client.cookies.set("nordic_session", _SESSION_ID)
        response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json()["data"] == {"logged_out": True}
    assert "nordic_session=" in response.headers["set-cookie"]
    assert authentication.logout_calls == 1


def test_login_rate_limit_has_retry_after_and_store_outage_fails_closed() -> None:
    blocked_client, _authentication = _client(limiter=_BlockingLimiter())
    with blocked_client:
        blocked = blocked_client.post(
            "/api/auth/login",
            json={"email": "user@demo.invalid", "password": "anything"},
        )
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "42"
    assert "user@demo.invalid" not in blocked.text

    unavailable_client, _authentication = _client(limiter=_UnavailableLimiter())
    with unavailable_client:
        unavailable = unavailable_client.post(
            "/api/auth/login",
            json={"email": "user@demo.invalid", "password": "anything"},
        )
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "authentication_unavailable"
