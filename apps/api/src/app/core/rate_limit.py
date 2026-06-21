"""Redis-backed, fail-closed fixed-window rate limiting."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

from redis.exceptions import RedisError

from app.core.session_store import AuthStateUnavailableError, RedisClient

_EMAIL_PREFIX = "auth:rate:email:"
_ORIGIN_PREFIX = "auth:rate:origin:"
_ROUTE_PREFIX = "api:rate:"

_CHECK_LIMIT_SCRIPT = """
local email_count = redis.call('INCR', KEYS[1])
if email_count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[3]) end
local origin_count = redis.call('INCR', KEYS[2])
if origin_count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[3]) end
local email_ttl = redis.call('TTL', KEYS[1])
local origin_ttl = redis.call('TTL', KEYS[2])
local allowed = 1
if email_count > tonumber(ARGV[1]) or origin_count > tonumber(ARGV[2]) then allowed = 0 end
return {allowed, email_ttl, origin_ttl}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    """Publicly safe result of a login-attempt counter check."""

    allowed: bool
    retry_after_seconds: int | None = None


class RateLimitUnavailableError(RuntimeError):
    """The rate-limit store could not safely decide whether work may proceed."""


@dataclass(frozen=True)
class RouteRateLimitPolicy:
    """One server-owned route bucket and its subject/client fixed-window bounds."""

    bucket: str
    user_attempts: int
    origin_attempts: int
    window_seconds: int


class LoginRateLimiter(Protocol):
    """The rate-limiter boundary used by public login handlers."""

    async def check(self, normalized_email: str, client_origin: str) -> RateLimitDecision: ...


class RouteRateLimiter(Protocol):
    """Rate-limit boundary for protected expensive or mutating API operations."""

    async def check(
        self,
        policy: RouteRateLimitPolicy,
        *,
        user_id: str,
        client_origin: str,
    ) -> RateLimitDecision: ...


class RedisLoginRateLimiter:
    """Atomic fixed-window limiter for normalized-email and client-origin scopes."""

    def __init__(
        self,
        client: RedisClient,
        *,
        digest_key: bytes,
        email_attempts: int,
        origin_attempts: int,
        window_seconds: int,
    ) -> None:
        self._client = client
        self._digest_key = digest_key
        self._email_attempts = email_attempts
        self._origin_attempts = origin_attempts
        self._window_seconds = window_seconds

    async def check(self, normalized_email: str, client_origin: str) -> RateLimitDecision:
        email_key = _derived_key(_EMAIL_PREFIX, self._digest_key, normalized_email)
        origin_key = _derived_key(_ORIGIN_PREFIX, self._digest_key, client_origin)
        try:
            result = await cast(
                Awaitable[object],
                self._client.eval(
                    _CHECK_LIMIT_SCRIPT,
                    2,
                    email_key,
                    origin_key,
                    str(self._email_attempts),
                    str(self._origin_attempts),
                    str(self._window_seconds),
                ),
            )
        except RedisError as error:
            raise AuthStateUnavailableError("Authentication state is unavailable.") from error
        if not isinstance(result, list) or len(result) != 3:
            raise AuthStateUnavailableError("Authentication state is unavailable.")
        allowed = _as_int(result[0])
        email_ttl = _as_int(result[1])
        origin_ttl = _as_int(result[2])
        if allowed is None or email_ttl is None or origin_ttl is None:
            raise AuthStateUnavailableError("Authentication state is unavailable.")
        if allowed == 1:
            return RateLimitDecision(allowed=True)
        # Redis may report -1/-2 in unusual expiry races. The configured window
        # is a safe conservative retry interval in that case.
        retry_after = max(email_ttl, origin_ttl, 1)
        if retry_after > self._window_seconds:
            retry_after = self._window_seconds
        return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)


class RedisRouteRateLimiter:
    """Atomic fixed-window limiter with HMAC-derived user/client Redis keys."""

    def __init__(self, client: RedisClient, *, digest_key: bytes) -> None:
        self._client = client
        self._digest_key = digest_key

    async def check(
        self,
        policy: RouteRateLimitPolicy,
        *,
        user_id: str,
        client_origin: str,
    ) -> RateLimitDecision:
        user_key = _derived_key(f"{_ROUTE_PREFIX}{policy.bucket}:user:", self._digest_key, user_id)
        origin_key = _derived_key(
            f"{_ROUTE_PREFIX}{policy.bucket}:origin:", self._digest_key, client_origin
        )
        try:
            result = await cast(
                Awaitable[object],
                self._client.eval(
                    _CHECK_LIMIT_SCRIPT,
                    2,
                    user_key,
                    origin_key,
                    str(policy.user_attempts),
                    str(policy.origin_attempts),
                    str(policy.window_seconds),
                ),
            )
        except RedisError as error:
            raise RateLimitUnavailableError("Rate limit state is unavailable.") from error
        return _decision_from_redis_result(result, window_seconds=policy.window_seconds)


class InMemoryLoginRateLimiter:
    """Deterministic fixed-window test double; it stores only derived keys."""

    def __init__(
        self,
        *,
        digest_key: bytes = b"test-rate-limit-key",
        email_attempts: int = 5,
        origin_attempts: int = 20,
        window_seconds: int = 900,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._digest_key = digest_key
        self._email_attempts = email_attempts
        self._origin_attempts = origin_attempts
        self._window_seconds = window_seconds
        self._now = now if now is not None else lambda: datetime.now(UTC)
        self._counters: dict[str, tuple[int, datetime]] = {}

    async def check(self, normalized_email: str, client_origin: str) -> RateLimitDecision:
        now = self._now()
        email_key = _derived_key(_EMAIL_PREFIX, self._digest_key, normalized_email)
        origin_key = _derived_key(_ORIGIN_PREFIX, self._digest_key, client_origin)
        email_count, email_expires_at = self._increment(email_key, now)
        origin_count, origin_expires_at = self._increment(origin_key, now)
        if email_count <= self._email_attempts and origin_count <= self._origin_attempts:
            return RateLimitDecision(allowed=True)
        seconds = max(
            1,
            int(max(email_expires_at, origin_expires_at).timestamp() - now.timestamp() + 0.999),
        )
        return RateLimitDecision(allowed=False, retry_after_seconds=seconds)

    def _increment(self, key: str, now: datetime) -> tuple[int, datetime]:
        count, expires_at = self._counters.get(key, (0, now))
        if expires_at <= now:
            count = 0
            expires_at = now + timedelta(seconds=self._window_seconds)
        count += 1
        self._counters[key] = (count, expires_at)
        return count, expires_at


def _derived_key(prefix: str, secret: bytes, source: str) -> str:
    """Return an HMAC-derived Redis key that reveals no email or IP address."""

    digest = hmac.new(secret, source.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{prefix}{digest}"


class InMemoryRouteRateLimiter:
    """Deterministic test double for protected route limits."""

    def __init__(
        self,
        *,
        digest_key: bytes = b"test-rate-limit-key",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._digest_key = digest_key
        self._now = now if now is not None else lambda: datetime.now(UTC)
        self._counters: dict[str, tuple[int, datetime]] = {}

    async def check(
        self,
        policy: RouteRateLimitPolicy,
        *,
        user_id: str,
        client_origin: str,
    ) -> RateLimitDecision:
        now = self._now()
        user_key = _derived_key(f"{_ROUTE_PREFIX}{policy.bucket}:user:", self._digest_key, user_id)
        origin_key = _derived_key(
            f"{_ROUTE_PREFIX}{policy.bucket}:origin:", self._digest_key, client_origin
        )
        user_count, user_expires_at = self._increment(user_key, now, policy.window_seconds)
        origin_count, origin_expires_at = self._increment(origin_key, now, policy.window_seconds)
        if user_count <= policy.user_attempts and origin_count <= policy.origin_attempts:
            return RateLimitDecision(allowed=True)
        seconds = max(
            1,
            int(max(user_expires_at, origin_expires_at).timestamp() - now.timestamp() + 0.999),
        )
        return RateLimitDecision(allowed=False, retry_after_seconds=seconds)

    def _increment(self, key: str, now: datetime, window_seconds: int) -> tuple[int, datetime]:
        count, expires_at = self._counters.get(key, (0, now))
        if expires_at <= now:
            count = 0
            expires_at = now + timedelta(seconds=window_seconds)
        count += 1
        self._counters[key] = (count, expires_at)
        return count, expires_at


def _decision_from_redis_result(result: object, *, window_seconds: int) -> RateLimitDecision:
    """Validate one Lua response and convert it into a safe public decision."""

    if not isinstance(result, list) or len(result) != 3:
        raise RateLimitUnavailableError("Rate limit state is unavailable.")
    allowed = _as_int(result[0])
    user_ttl = _as_int(result[1])
    origin_ttl = _as_int(result[2])
    if allowed is None or user_ttl is None or origin_ttl is None:
        raise RateLimitUnavailableError("Rate limit state is unavailable.")
    if allowed == 1:
        return RateLimitDecision(allowed=True)
    retry_after = min(max(user_ttl, origin_ttl, 1), window_seconds)
    return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)


def _as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="ignore")
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
