"""Tenant-bound controlled-memory persistence queries."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import asc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.memory import MemoryEntry, MemoryUsageRecord


class MemoryRepository:
    """Persist governed records only; policy and store synchronization live in the service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_update(
        self, organization_id: UUID, entry_id: UUID, *, include_archived: bool = False
    ) -> MemoryEntry | None:
        statement = select(MemoryEntry).where(
            MemoryEntry.organization_id == organization_id,
            MemoryEntry.id == entry_id,
        )
        if not include_archived:
            statement = statement.where(MemoryEntry.archived_at.is_(None))
        return cast(MemoryEntry | None, await self.session.scalar(statement.with_for_update()))

    async def list_organization(
        self, organization_id: UUID, *, include_archived: bool
    ) -> tuple[MemoryEntry, ...]:
        statement = select(MemoryEntry).where(
            MemoryEntry.organization_id == organization_id,
            MemoryEntry.memory_scope == "organization",
        )
        if not include_archived:
            statement = statement.where(MemoryEntry.archived_at.is_(None))
        statement = statement.order_by(
            asc(MemoryEntry.memory_type), asc(MemoryEntry.updated_at), asc(MemoryEntry.id)
        )
        return tuple((await self.session.scalars(statement)).all())

    async def list_active_for_drafting(
        self, organization_id: UUID, user_id: UUID
    ) -> tuple[MemoryEntry, ...]:
        statement = (
            select(MemoryEntry)
            .where(
                MemoryEntry.organization_id == organization_id,
                MemoryEntry.is_active.is_(True),
                MemoryEntry.archived_at.is_(None),
                or_(
                    MemoryEntry.memory_scope == "organization",
                    (MemoryEntry.memory_scope == "user") & (MemoryEntry.user_id == user_id),
                ),
            )
            .order_by(
                asc(MemoryEntry.memory_type),
                asc(MemoryEntry.updated_at),
                asc(MemoryEntry.id),
            )
            .limit(4)
        )
        return tuple((await self.session.scalars(statement)).all())

    async def create(self, entry: MemoryEntry) -> MemoryEntry:
        self.session.add(entry)
        return entry

    async def create_usage(self, record: MemoryUsageRecord) -> MemoryUsageRecord:
        self.session.add(record)
        return record
