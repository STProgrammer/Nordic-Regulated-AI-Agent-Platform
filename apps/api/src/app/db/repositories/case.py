"""Tenant-safe persistence queries for case records, without case-domain policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.case import Case
from app.db.models.identity import User
from app.db.repositories.base import ArchivableTenantScopedRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec, resolve_sort


class Unset(Enum):
    """Internal marker that keeps an omitted update distinct from an explicit null."""

    VALUE = "unset"


@dataclass(frozen=True)
class CaseFilters:
    """Approved list filters; each is safely combined with the tenant predicate."""

    status: str | None = None
    risk_level: str | None = None
    assigned_user_id: UUID | None = None
    domain: str | None = None
    priority: str | None = None
    search_text: str | None = None


@dataclass(frozen=True)
class CaseUpdateValues:
    """Explicit storage changes with an internal omitted-field marker."""

    title: str | Unset = Unset.VALUE
    description: str | Unset = Unset.VALUE
    language: str | Unset = Unset.VALUE
    domain: str | Unset = Unset.VALUE
    case_type: str | None | Unset = Unset.VALUE
    priority: str | Unset = Unset.VALUE
    status: str | Unset = Unset.VALUE
    risk_level: str | None | Unset = Unset.VALUE
    assigned_user_id: UUID | None | Unset = Unset.VALUE
    due_date: date | None | Unset = Unset.VALUE
    external_reference: str | None | Unset = Unset.VALUE


class CaseRepository(ArchivableTenantScopedRepository[Case]):
    """Persistence-only case access with explicit tenant and archive predicates."""

    _sort_columns = {
        "inserted_at": cast(ColumnElement[object], Case.inserted_at),
        "case_number": cast(ColumnElement[object], Case.case_number),
        "updated_at": cast(ColumnElement[object], Case.updated_at),
        "title": cast(ColumnElement[object], Case.title),
        "due_date": cast(ColumnElement[object], Case.due_date),
        "priority": cast(ColumnElement[object], Case.priority),
        "status": cast(ColumnElement[object], Case.status),
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

    async def list_assignee_options(self, organization_id: UUID) -> tuple[tuple[UUID, str], ...]:
        """Return only active users assigned to visible current-tenant cases.

        The Case Inbox needs human-readable filter choices, but it must not
        broaden the Admin-only Users API into a directory.  Joining from active
        cases keeps this read model both minimal and subject to the same tenant
        and archive scope as the Case list.
        """

        statement = (
            select(User.id, User.display_name)
            .join(
                Case,
                (Case.assigned_user_id == User.id) & (Case.organization_id == User.organization_id),
            )
            .where(
                Case.organization_id == organization_id,
                Case.archived_at.is_(None),
                User.organization_id == organization_id,
                User.is_active.is_(True),
            )
            .distinct()
            .order_by(User.display_name.asc(), User.id.asc())
        )
        rows = (await self.session.execute(statement)).all()
        return tuple((user_id, display_name) for user_id, display_name in rows)

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        filters: CaseFilters | None = None,
        sort: SortSpec | None = None,
        include_archived: bool = False,
    ) -> Page[Case]:
        """List non-archived tenant cases through bounded, typed predicates."""

        selected_filters = filters if filters is not None else CaseFilters()
        additional: list[ColumnElement[bool]] = []
        if selected_filters.status is not None:
            additional.append(Case.status == selected_filters.status)
        if selected_filters.risk_level is not None:
            additional.append(Case.risk_level == selected_filters.risk_level)
        if selected_filters.assigned_user_id is not None:
            additional.append(Case.assigned_user_id == selected_filters.assigned_user_id)
        if selected_filters.domain is not None:
            additional.append(Case.domain == selected_filters.domain)
        if selected_filters.priority is not None:
            additional.append(Case.priority == selected_filters.priority)
        if selected_filters.search_text is not None:
            normalized = selected_filters.search_text.casefold()
            pattern = f"%{normalized}%"
            additional.append(
                or_(
                    func.lower(Case.case_number).like(pattern),
                    func.lower(Case.title).like(pattern),
                    func.lower(Case.description).like(pattern),
                )
            )
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
            additional=tuple(additional),
        )

    async def update(self, case: Case, values: CaseUpdateValues) -> Case:
        """Persist values selected by the Case domain service only."""

        if not isinstance(values.title, Unset):
            case.title = values.title
        if not isinstance(values.description, Unset):
            case.description = values.description
        if not isinstance(values.language, Unset):
            case.language = values.language
        if not isinstance(values.domain, Unset):
            case.domain = values.domain
        if not isinstance(values.case_type, Unset):
            case.case_type = values.case_type
        if not isinstance(values.priority, Unset):
            case.priority = values.priority
        if not isinstance(values.status, Unset):
            case.status = values.status
        if not isinstance(values.risk_level, Unset):
            case.risk_level = values.risk_level
        if not isinstance(values.assigned_user_id, Unset):
            case.assigned_user_id = values.assigned_user_id
        if not isinstance(values.due_date, Unset):
            case.due_date = values.due_date
        if not isinstance(values.external_reference, Unset):
            case.external_reference = values.external_reference
        return case

    async def archive(self, organization_id: UUID, record_id: UUID) -> Case | None:
        """Atomically archive a visible case and persist its terminal status."""

        statement = (
            update(Case)
            .where(
                *self.scoped_predicates(
                    organization_id,
                    additional=(Case.id == record_id,),
                )
            )
            .values(archived_at=datetime.now(UTC), status="archived")
            .returning(Case)
        )
        return cast(Case | None, await self.session.scalar(statement))
