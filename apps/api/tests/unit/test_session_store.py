from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.session_store import InMemorySessionStore


def test_session_expiry_logout_and_user_wide_invalidation() -> None:
    current = datetime(2026, 1, 1, tzinfo=UTC)

    def now() -> datetime:
        return current

    async def exercise() -> None:
        nonlocal current
        store = InMemorySessionStore(now=now)
        user_id = uuid4()
        organization_id = uuid4()
        first = await store.create(user_id, organization_id, ttl_seconds=60)
        second = await store.create(user_id, organization_id, ttl_seconds=60)

        assert await store.get(first) is not None
        await store.delete(first)
        assert await store.get(first) is None
        await store.delete_all_for_user(user_id)
        assert await store.get(second) is None

        expired = await store.create(user_id, organization_id, ttl_seconds=60)
        current += timedelta(seconds=61)
        assert await store.get(expired) is None

    import asyncio

    asyncio.run(exercise())
