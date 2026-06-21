from __future__ import annotations

from typing import Annotated

from app.api.dependencies import get_route_rate_limiter
from app.api.route_rate_limit import enforce_route_rate_limit
from app.core.config import AppSettings
from app.core.rate_limit import (
    RateLimitDecision,
    RateLimitUnavailableError,
    RouteRateLimitPolicy,
)
from app.main import create_api_app
from fastapi import Depends, Request
from fastapi.testclient import TestClient

_POLICY = RouteRateLimitPolicy(
    bucket="workflow",
    user_attempts=10,
    origin_attempts=40,
    window_seconds=900,
)


class _BlockingLimiter:
    async def check(self, *_args: object, **_kwargs: object) -> RateLimitDecision:
        return RateLimitDecision(allowed=False, retry_after_seconds=73)


class _UnavailableLimiter:
    async def check(self, *_args: object, **_kwargs: object) -> RateLimitDecision:
        raise RateLimitUnavailableError("synthetic outage")


def _client(limiter: object) -> tuple[TestClient, dict[str, int]]:
    app = create_api_app(AppSettings(environment="test"))
    calls = {"service": 0}
    app.dependency_overrides[get_route_rate_limiter] = lambda: limiter

    @app.post("/api/__test__/limited")
    async def limited(
        request: Request,
        resolved_limiter: Annotated[object, Depends(get_route_rate_limiter)],
    ) -> dict[str, bool]:
        await enforce_route_rate_limit(
            request,
            resolved_limiter,  # type: ignore[arg-type]
            _POLICY,
            user_id="synthetic-user",
        )
        calls["service"] += 1
        return {"ok": True}

    return TestClient(app), calls


def test_route_rate_limit_stops_work_and_returns_retry_after() -> None:
    client, calls = _client(_BlockingLimiter())
    with client:
        response = client.post("/api/__test__/limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "73"
    assert response.json()["error"]["code"] == "request_rate_limited"
    assert calls["service"] == 0


def test_route_rate_limit_fails_closed_when_redis_state_is_unavailable() -> None:
    client, calls = _client(_UnavailableLimiter())
    with client:
        response = client.post("/api/__test__/limited")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "security_state_unavailable"
    assert calls["service"] == 0
