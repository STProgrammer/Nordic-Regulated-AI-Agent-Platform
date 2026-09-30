"""Opaque server-side authentication sessions backed by Redis.

The browser receives only a cryptographically random handle. Trusted identity
and organization data stay in short-lived Redis state and are checked against
PostgreSQL on every protected request.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import UUID

from redis import asyncio as redis_asyncio
from redis.exceptions import RedisError

from app.core.config import AppSettings, get_settings

_SESSION_PREFIX = "auth:session:"
_USER_SESSION_PREFIX = "auth:user-sessions:"
_SESSION_VERSION = 1


class AuthStateUnavailableError(RuntimeError):
    """Volatile authentication state cannot be read or written safely."""


@dataclass(frozen=True)
class SessionRecord:
    """Trusted server-side data associated with one opaque session handle."""

    user_id: UUID
    organization_id: UUID
    issued_at: datetime
    expires_at: datetime
    version: int = _SESSION_VERSION


class SessionStore(Protocol):
    """Minimal session operations used by the authentication service."""

    async def issue(self, user_id: UUID, organization_id: UUID, *, ttl_seconds: int) -> str: ...

    async def get(self, session_id: str) -> SessionRecord | None: ...

    async def delete(self, session_id: str) -> None: ...

    async def delete_all_for_user(self, user_id: UUID) -> None: ...


RedisClient = redis_asyncio.Redis
_redis_clients: dict[str, RedisClient] = {}


def get_redis_client(settings: AppSettings | None = None) -> RedisClient:
    """Return a lazy Redis client; no connection occurs until an operation."""

    resolved_settings = settings if settings is not None else get_settings()
    redis_url = resolved_settings.redis_async_url()
    client = _redis_clients.get(redis_url)
    if client is None:
        client = redis_asyncio.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=resolved_settings.redis_socket_timeout_seconds,
            socket_timeout=resolved_settings.redis_socket_timeout_seconds,
        )
        _redis_clients[redis_url] = client
    return client


async def dispose_redis_clients() -> None:
    """Close every lazily-initialized Redis client during shutdown/tests."""

    clients = tuple(_redis_clients.values())
    _redis_clients.clear()
    for client in clients:
        await client.aclose()


def _session_key(session_id: str) -> str:
    return f"{_SESSION_PREFIX}{session_id}"


def _user_sessions_key(user_id: UUID) -> str:
    return f"{_USER_SESSION_PREFIX}{user_id}"


def _serialize(record: SessionRecord) -> str:
    values = asdict(record)
    values["user_id"] = str(record.user_id)
    values["organization_id"] = str(record.organization_id)
    values["issued_at"] = record.issued_at.isoformat()
    values["expires_at"] = record.expires_at.isoformat()
    return json.dumps(values, separators=(",", ":"), sort_keys=True)


def _deserialize(value: str) -> SessionRecord | None:
    """Parse only the bounded schema expected for session data."""

    try:
        raw = cast(dict[str, object], json.loads(value))
        if set(raw) != {"expires_at", "issued_at", "organization_id", "user_id", "version"}:
            return None
        version = raw["version"]
        if version != _SESSION_VERSION:
            return None
        issued_at = datetime.fromisoformat(str(raw["issued_at"]))
        expires_at = datetime.fromisoformat(str(raw["expires_at"]))
        if issued_at.tzinfo is None or expires_at.tzinfo is None:
            return None
        return SessionRecord(
            user_id=UUID(str(raw["user_id"])),
            organization_id=UUID(str(raw["organization_id"])),
            issued_at=issued_at.astimezone(UTC),
            expires_at=expires_at.astimezone(UTC),
            version=version,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


class RedisSessionStore:
    """Redis implementation with per-user invalidation support."""

    def __init__(self, client: RedisClient) -> None:
        self._client = client

    async def issue(self, user_id: UUID, organization_id: UUID, *, ttl_seconds: int) -> str:
        session_id = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        record = SessionRecord(
            user_id=user_id,
            organization_id=organization_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        try:
            async with self._client.pipeline(transaction=True) as pipeline:
                pipeline.set(_session_key(session_id), _serialize(record), ex=ttl_seconds)
                pipeline.sadd(_user_sessions_key(user_id), session_id)
                pipeline.expire(_user_sessions_key(user_id), ttl_seconds)
                await pipeline.execute()
        except RedisError as error:
            raise AuthStateUnavailableError("Authentication state is unavailable.") from error
        return session_id

    async def get(self, session_id: str) -> SessionRecord | None:
        if not _is_plausible_session_id(session_id):
            return None
        try:
            value = await self._client.get(_session_key(session_id))
        except RedisError as error:
            raise AuthStateUnavailableError("Authentication state is unavailable.") from error
        if value is None:
            return None
        record = _deserialize(value)
        if record is None or record.expires_at <= datetime.now(UTC):
            await self.delete(session_id)
            return None
        return record

    async def delete(self, session_id: str) -> None:
        if not _is_plausible_session_id(session_id):
            return
        try:
            value = await self._client.get(_session_key(session_id))
            record = _deserialize(value) if value is not None else None
            async with self._client.pipeline(transaction=True) as pipeline:
                pipeline.delete(_session_key(session_id))
                if record is not None:
                    pipeline.srem(_user_sessions_key(record.user_id), session_id)
                await pipeline.execute()
        except RedisError as error:
            raise AuthStateUnavailableError("Authentication state is unavailable.") from error

    async def delete_all_for_user(self, user_id: UUID) -> None:
        index_key = _user_sessions_key(user_id)
        try:
            session_ids = await cast(Awaitable[set[str]], self._client.smembers(index_key))
            async with self._client.pipeline(transaction=True) as pipeline:
                for session_id in session_ids:
                    if _is_plausible_session_id(session_id):
                        pipeline.delete(_session_key(session_id))
                pipeline.delete(index_key)
                await pipeline.execute()
        except RedisError as error:
            raise AuthStateUnavailableError("Authentication state is unavailable.") from error


class InMemorySessionStore:
    """Deterministic session-store double for focused tests."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now if now is not None else lambda: datetime.now(UTC)
        self._records: dict[str, SessionRecord] = {}
        self._user_sessions: dict[UUID, set[str]] = {}

    async def issue(self, user_id: UUID, organization_id: UUID, *, ttl_seconds: int) -> str:
        session_id = secrets.token_urlsafe(32)
        now = self._now()
        self._records[session_id] = SessionRecord(
            user_id=user_id,
            organization_id=organization_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._user_sessions.setdefault(user_id, set()).add(session_id)
        return session_id

    async def get(self, session_id: str) -> SessionRecord | None:
        record = self._records.get(session_id)
        if record is None:
            return None
        if record.expires_at <= self._now():
            await self.delete(session_id)
            return None
        return record

    async def delete(self, session_id: str) -> None:
        record = self._records.pop(session_id, None)
        if record is None:
            return
        sessions = self._user_sessions.get(record.user_id)
        if sessions is not None:
            sessions.discard(session_id)
            if not sessions:
                self._user_sessions.pop(record.user_id, None)

    async def delete_all_for_user(self, user_id: UUID) -> None:
        for session_id in tuple(self._user_sessions.get(user_id, set())):
            self._records.pop(session_id, None)
        self._user_sessions.pop(user_id, None)


def _is_plausible_session_id(value: str) -> bool:
    """Avoid issuing Redis operations for arbitrary unbounded cookie values."""

    return 32 <= len(value) <= 128 and all(
        character.isascii() and (character.isalnum() or character in "-_") for character in value
    )
