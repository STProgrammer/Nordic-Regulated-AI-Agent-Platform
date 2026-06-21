from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.core.rate_limit import (
    InMemoryLoginRateLimiter,
    InMemoryRouteRateLimiter,
    RouteRateLimitPolicy,
)


def test_fixed_window_limit_uses_derived_non_sensitive_keys() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)

    def now() -> datetime:
        return current

    async def exercise() -> None:
        nonlocal current
        limiter = InMemoryLoginRateLimiter(
            email_attempts=2,
            origin_attempts=4,
            window_seconds=60,
            now=now,
        )
        assert (await limiter.check("user@demo.invalid", "127.0.0.1")).allowed is True
        assert (await limiter.check("user@demo.invalid", "127.0.0.1")).allowed is True
        blocked = await limiter.check("user@demo.invalid", "127.0.0.1")
        assert blocked.allowed is False
        assert blocked.retry_after_seconds is not None
        assert all(
            "user@demo.invalid" not in key and "127.0.0.1" not in key for key in limiter._counters
        )

        current += timedelta(seconds=61)
        assert (await limiter.check("user@demo.invalid", "127.0.0.1")).allowed is True

    asyncio.run(exercise())


def test_route_limits_are_bucketed_and_use_derived_user_and_client_keys() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)

    def now() -> datetime:
        return current

    async def exercise() -> None:
        nonlocal current
        limiter = InMemoryRouteRateLimiter(now=now)
        policy = RouteRateLimitPolicy(
            bucket="workflow",
            user_attempts=2,
            origin_attempts=4,
            window_seconds=60,
        )
        assert (
            await limiter.check(policy, user_id="user-123", client_origin="127.0.0.1")
        ).allowed is True
        assert (
            await limiter.check(policy, user_id="user-123", client_origin="127.0.0.1")
        ).allowed is True
        blocked = await limiter.check(policy, user_id="user-123", client_origin="127.0.0.1")

        assert blocked.allowed is False
        assert blocked.retry_after_seconds is not None
        assert all("user-123" not in key and "127.0.0.1" not in key for key in limiter._counters)

        current += timedelta(seconds=61)
        assert (
            await limiter.check(policy, user_id="user-123", client_origin="127.0.0.1")
        ).allowed is True

    asyncio.run(exercise())
