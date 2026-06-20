"""Tenant-safe persistence queries for case records, without case-domain policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.case import Case
from app.db.repositories.base import ArchivableTenantScopedRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec, resolve_sort


@dataclass(frozen=True)
class CaseUpdateValues:
    """Explicit storage fields a future domain service may choose to change."""

    title: str | None = None
    description: str | None = None
    language: str | None = None
    domain: str | None = None
    case_type: str | None = None
    priority: str | None = None
    status: str | None = None
    risk_level: str | None = None
    assigned_user_id: UUID | None = None
    due_date: date | None = None
    external_reference: str | None = None


class CaseRepository(ArchivableTenantScopedRepository[Case]):
    """Persistence-only case access with explicit tenant and archive predicates."""

    _sort_columns = {
        "inserted_at": cast(ColumnElement[object], Case.inserted_at),
        "case_number": cast(ColumnElement[object], Case.case_number),
        "updated_at": cast(ColumnElement[object], Case.updated_at),
    }

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session,
            Case,
            id_column=cast(ColumnElement[UUID], Case.id),
            organization_column=cast(ColumnElement[UUID], Case.organization_id),
            archived_at_column=cast(ColumnElement[datetime | None], Case.archived_at),
        )

    async def create(self, case: Case) -> Case:
        self.session.add(case)
        return case

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
        include_archived: bool = False,
    ) -> Page[Case]:
        order = resolve_sort(
            sort,
            allowed=self._sort_columns,
            default=SortSpec("inserted_at"),
            tie_breaker=cast(ColumnElement[object], Case.id),
        )
        return await self.list_page(
            organization_id,
            pagination=pagination,
            order_by=order,
            include_archived=include_archived,
        )

    async def update(self, case: Case, values: CaseUpdateValues) -> Case:
        """Persist supplied storage values; case transition policy remains external."""

        if values.title is not None:
            case.title = values.title
        if values.description is not None:
            case.description = values.description
        if values.language is not None:
            case.language = values.language
        if values.domain is not None:
            case.domain = values.domain
        if values.case_type is not None:
            case.case_type = values.case_type
        if values.priority is not None:
            case.priority = values.priority
        if values.status is not None:
            case.status = values.status
        if values.risk_level is not None:
            case.risk_level = values.risk_level
        if values.assigned_user_id is not None:
            case.assigned_user_id = values.assigned_user_id
        if values.due_date is not None:
            case.due_date = values.due_date
        if values.external_reference is not None:
            case.external_reference = values.external_reference
        return case
