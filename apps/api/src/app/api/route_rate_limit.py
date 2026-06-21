"""Shared enforcement for protected API rate-limit policies."""

from __future__ import annotations

from fastapi import Request, status

from app.core.errors import ApiError
from app.core.rate_limit import RateLimitUnavailableError, RouteRateLimiter, RouteRateLimitPolicy


async def enforce_route_rate_limit(
    request: Request,
    limiter: RouteRateLimiter,
    policy: RouteRateLimitPolicy,
    *,
    user_id: str,
) -> None:
    """Stop protected work before it reaches its service when the store disallows it."""

    client = request.client
    client_origin = client.host if client is not None else "unknown-client"
    try:
        decision = await limiter.check(
            policy,
            user_id=user_id,
            client_origin=client_origin,
        )
    except RateLimitUnavailableError as error:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="security_state_unavailable",
            message="Request security state is temporarily unavailable.",
        ) from error
    if decision.allowed:
        return
    retry_after = decision.retry_after_seconds if decision.retry_after_seconds is not None else 1
    raise ApiError(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="request_rate_limited",
        message="Too many requests. Try again later.",
        response_headers={"Retry-After": str(retry_after)},
    )
