"""Tenant-safe persistence for workflow-run records without orchestration logic."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.workflow import WorkflowRun
from app.db.repositories.base import TenantScopedRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec, resolve_sort


class WorkflowRunRepository(TenantScopedRepository[WorkflowRun]):
    """Persistence-only workflow run access with an explicit organization predicate."""

    _sort_columns = {
        "started_at": cast(ColumnElement[object], WorkflowRun.started_at),
        "inserted_at": cast(ColumnElement[object], WorkflowRun.inserted_at),
        "workflow_name": cast(ColumnElement[object], WorkflowRun.workflow_name),
    }

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session,
            WorkflowRun,
            id_column=cast(ColumnElement[UUID], WorkflowRun.id),
            organization_column=cast(ColumnElement[UUID], WorkflowRun.organization_id),
            archived_at_column=None,
        )

    async def create(self, workflow_run: WorkflowRun) -> WorkflowRun:
        self.session.add(workflow_run)
        return workflow_run

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
    ) -> Page[WorkflowRun]:
        order = resolve_sort(
            sort,
            allowed=self._sort_columns,
            default=SortSpec("started_at"),
            tie_breaker=cast(ColumnElement[object], WorkflowRun.id),
        )
        return await self.list_page(organization_id, pagination=pagination, order_by=order)
