"""A narrow LangGraph-store adapter with server-derived namespaces only."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from langgraph.store.postgres.aio import AsyncPostgresStore

from agent_orchestrator.memory.policy import MemoryScope

_PREFIX = "nordic-regulated-ai"


class ControlledMemoryStore(Protocol):
    """The only store operations needed by the controlled-memory service."""

    async def put(
        self, *, organization_id: UUID, user_id: UUID | None, key: str, value: dict[str, object]
    ) -> None: ...

    async def get(
        self, *, organization_id: UUID, user_id: UUID | None, key: str
    ) -> dict[str, object] | None: ...

    async def delete(self, *, organization_id: UUID, user_id: UUID | None, key: str) -> None: ...


def namespace_for(*, organization_id: UUID, user_id: UUID | None) -> tuple[str, ...]:
    """Construct the fixed hierarchical namespace from trusted UUIDs."""

    namespace = (_PREFIX, "organization", str(organization_id))
    if user_id is None:
        return namespace + (MemoryScope.ORGANIZATION.value,)
    return namespace + (MemoryScope.USER.value, str(user_id))


class PostgresControlledMemoryStore:
    """Persistent Postgres store compatible with LangMem/LangGraph memory APIs.

    No semantic index is configured and no generic LangMem manage/search tool is
    exposed. Every call opens a short-lived store connection to avoid sharing a
    mutable connection across API requests and Celery task event loops.
    """

    def __init__(self, connection_string: str) -> None:
        if not connection_string.startswith(("postgresql://", "postgres://")):
            raise ValueError("Controlled memory requires a PostgreSQL store URL.")
        self._connection_string = connection_string

    @asynccontextmanager
    async def _store(self) -> AsyncIterator[AsyncPostgresStore]:
        async with AsyncPostgresStore.from_conn_string(self._connection_string) as store:
            # The package-owned schema is required once; setup is idempotent and
            # eliminates a process-local fallback when a new worker starts.
            await store.setup()
            yield store

    async def put(
        self, *, organization_id: UUID, user_id: UUID | None, key: str, value: dict[str, object]
    ) -> None:
        async with self._store() as store:
            namespace = namespace_for(organization_id=organization_id, user_id=user_id)
            await store.aput(namespace, key, value, index=False)

    async def get(
        self, *, organization_id: UUID, user_id: UUID | None, key: str
    ) -> dict[str, object] | None:
        async with self._store() as store:
            namespace = namespace_for(organization_id=organization_id, user_id=user_id)
            item = await store.aget(namespace, key)
        if item is None or not isinstance(item.value, dict):
            return None
        return {str(name): value for name, value in item.value.items()}

    async def delete(self, *, organization_id: UUID, user_id: UUID | None, key: str) -> None:
        async with self._store() as store:
            namespace = namespace_for(organization_id=organization_id, user_id=user_id)
            await store.adelete(namespace, key)


@dataclass
class InMemoryControlledMemoryStore:
    """Test-only fake; application dependencies never construct this implementation."""

    _values: dict[tuple[tuple[str, ...], str], dict[str, object]] = field(default_factory=dict)

    async def put(
        self, *, organization_id: UUID, user_id: UUID | None, key: str, value: dict[str, object]
    ) -> None:
        namespace = namespace_for(organization_id=organization_id, user_id=user_id)
        self._values[(namespace, key)] = dict(value)

    async def get(
        self, *, organization_id: UUID, user_id: UUID | None, key: str
    ) -> dict[str, object] | None:
        namespace = namespace_for(organization_id=organization_id, user_id=user_id)
        value = self._values.get((namespace, key))
        return None if value is None else dict(value)

    async def delete(self, *, organization_id: UUID, user_id: UUID | None, key: str) -> None:
        namespace = namespace_for(organization_id=organization_id, user_id=user_id)
        self._values.pop((namespace, key), None)
