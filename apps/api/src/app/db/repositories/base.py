"""Small tenant-safe SQLAlchemy repository primitives.

Repositories receive a caller-owned session and never commit or roll back it.
All tenant methods require the organization id in their database predicates, so
another tenant's UUID is indistinguishable from a missing record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.services.common.pagination import Page, Pagination


class TenantScopedRepository[T]:
    """Shared get/list/archive behavior for a deliberately narrow tenant model."""

    def __init__(
        self,
        session: AsyncSession,
        model: type[T],
        *,
        id_column: ColumnElement[UUID],
        organization_column: ColumnElement[UUID],
        archived_at_column: ColumnElement[datetime | None] | None,
    ) -> None:
        self.session = session
        self.model = model
        self._id_column = id_column
        self._organization_column = organization_column
        self._archived_at_column = archived_at_column

    def scoped_predicates(
        self,
        organization_id: UUID,
        *,
        include_archived: bool = False,
        additional: tuple[ColumnElement[bool], ...] = (),
    ) -> tuple[ColumnElement[bool], ...]:
        """Return the single shared source of tenant/archive filters for a query."""

        predicates: list[ColumnElement[bool]] = [self._organization_column == organization_id]
        if self._archived_at_column is not None and not include_archived:
            predicates.append(self._archived_at_column.is_(None))
        predicates.extend(additional)
        return tuple(predicates)

    async def get(
        self, organization_id: UUID, record_id: UUID, *, include_archived: bool = False
    ) -> T | None:
        """Find one record only within a tenant and requested archive scope."""

        statement = select(self.model).where(
            *self.scoped_predicates(
                organization_id,
                include_archived=include_archived,
                additional=(self._id_column == record_id,),
            )
        )
        return cast(T | None, await self.session.scalar(statement))

    async def list_page(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        order_by: tuple[ColumnElement[object], ...],
        include_archived: bool = False,
        additional: tuple[ColumnElement[bool], ...] = (),
    ) -> Page[T]:
        """Return a page and count using exactly the same tenant/archive filters."""

        predicates = self.scoped_predicates(
            organization_id, include_archived=include_archived, additional=additional
        )
        total_statement = select(func.count()).select_from(self.model).where(*predicates)
        total = await self.session.scalar(total_statement)
        rows_statement = (
            select(self.model)
            .where(*predicates)
            .order_by(*order_by)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        rows = tuple((await self.session.scalars(rows_statement)).all())
        return Page(
            items=rows,
            limit=pagination.limit,
            offset=pagination.offset,
            total=total if total is not None else 0,
        )


class ArchivableTenantScopedRepository[T](TenantScopedRepository[T]):
    """Tenant repository extension available only to models with an archive marker."""

    async def archive(self, organization_id: UUID, record_id: UUID) -> T | None:
        """Soft archive one visible tenant record."""

        if self._archived_at_column is None:
            raise RuntimeError("An archivable repository requires an archive column.")
        statement = (
            update(self.model)
            .where(
                *self.scoped_predicates(
                    organization_id,
                    additional=(self._id_column == record_id,),
                )
            )
            .values({self._archived_at_column: datetime.now(UTC)})
            .returning(self.model)
        )
        return cast(T | None, await self.session.scalar(statement))
