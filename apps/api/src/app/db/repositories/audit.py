"""Append-only, organization-scoped audit-event storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.audit import AuditEvent
from app.db.repositories.base import TenantScopedRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec, resolve_sort


@dataclass(frozen=True)
class AuditEventFilters:
    """Approved audit-list filters; no arbitrary database expression is accepted."""

    event_type: str | None = None
    resource_type: str | None = None
    case_id: UUID | None = None
    actor_user_id: UUID | None = None
    inserted_after: datetime | None = None
    inserted_before: datetime | None = None


class AuditEventRepository(TenantScopedRepository[AuditEvent]):
    """Only append and scoped read/list operations are available for audit rows."""

    _sort_columns = {
        "inserted_at": cast(ColumnElement[object], AuditEvent.inserted_at),
        "event_type": cast(ColumnElement[object], AuditEvent.event_type),
        "resource_type": cast(ColumnElement[object], AuditEvent.resource_type),
    }

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session,
            AuditEvent,
            id_column=cast(ColumnElement[UUID], AuditEvent.id),
            organization_column=cast(ColumnElement[UUID], AuditEvent.organization_id),
            archived_at_column=None,
        )

    async def append(self, event: AuditEvent) -> AuditEvent:
        """Stage an immutable audit row; update/delete operations are intentionally absent."""

        self.session.add(event)
        return event

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        filters: AuditEventFilters | None = None,
        sort: SortSpec | None = None,
    ) -> Page[AuditEvent]:
        """List audit events with safe filters layered on the tenant predicate."""

        selected_filters = filters if filters is not None else AuditEventFilters()
        additional: list[ColumnElement[bool]] = []
        if selected_filters.event_type is not None:
            additional.append(AuditEvent.event_type == selected_filters.event_type)
        if selected_filters.resource_type is not None:
            additional.append(AuditEvent.resource_type == selected_filters.resource_type)
        if selected_filters.case_id is not None:
            additional.append(AuditEvent.case_id == selected_filters.case_id)
        if selected_filters.actor_user_id is not None:
            additional.append(AuditEvent.actor_user_id == selected_filters.actor_user_id)
        if selected_filters.inserted_after is not None:
            additional.append(AuditEvent.inserted_at >= selected_filters.inserted_after)
        if selected_filters.inserted_before is not None:
            additional.append(AuditEvent.inserted_at <= selected_filters.inserted_before)
        order = resolve_sort(
            sort,
            allowed=self._sort_columns,
            default=SortSpec("inserted_at"),
            tie_breaker=cast(ColumnElement[object], AuditEvent.id),
        )
        return await self.list_page(
            organization_id,
            pagination=pagination,
            order_by=order,
            additional=tuple(additional),
        )
