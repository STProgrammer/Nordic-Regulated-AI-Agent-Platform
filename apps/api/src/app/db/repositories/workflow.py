"""Tenant-safe persistence for workflow-run records without orchestration logic."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.workflow import Approval, WorkflowNodeRun, WorkflowRun
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

    async def get_for_update(
        self, organization_id: UUID, workflow_run_id: UUID
    ) -> WorkflowRun | None:
        """Lock one tenant-owned run for an idempotent worker lifecycle transition."""

        statement = (
            select(WorkflowRun)
            .where(
                *self.scoped_predicates(
                    organization_id, additional=(WorkflowRun.id == workflow_run_id,)
                )
            )
            .with_for_update()
        )
        return cast(WorkflowRun | None, await self.session.scalar(statement))

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


class WorkflowNodeRunRepository:
    """Narrow node-trace persistence tied to an already scoped parent workflow run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, node_run: WorkflowNodeRun) -> WorkflowNodeRun:
        self.session.add(node_run)
        return node_run

    async def get_for_update(
        self, workflow_run_id: UUID, node_run_id: UUID
    ) -> WorkflowNodeRun | None:
        statement = (
            select(WorkflowNodeRun)
            .where(
                WorkflowNodeRun.workflow_run_id == workflow_run_id,
                WorkflowNodeRun.id == node_run_id,
            )
            .with_for_update()
        )
        return cast(WorkflowNodeRun | None, await self.session.scalar(statement))

    async def finish(
        self,
        node_run: WorkflowNodeRun,
        *,
        status: str,
        finished_at: datetime,
        duration_ms: int,
        output_summary: dict[str, object],
        retry_count: int,
        error_summary: str | None,
    ) -> WorkflowNodeRun:
        node_run.status = status
        node_run.finished_at = finished_at
        node_run.duration_ms = duration_ms
        node_run.output_summary = output_summary
        node_run.retry_count = retry_count
        node_run.error_summary = error_summary
        return node_run


class ApprovalRepository:
    """Tenant-scoped review persistence; authorization remains in the service layer."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, approval: Approval) -> Approval:
        self.session.add(approval)
        return approval

    async def get(self, organization_id: UUID, approval_id: UUID) -> Approval | None:
        statement = select(Approval).where(
            Approval.organization_id == organization_id,
            Approval.id == approval_id,
        )
        return cast(Approval | None, await self.session.scalar(statement))

    async def get_for_update(self, organization_id: UUID, approval_id: UUID) -> Approval | None:
        statement = (
            select(Approval)
            .where(
                Approval.organization_id == organization_id,
                Approval.id == approval_id,
            )
            .with_for_update()
        )
        return cast(Approval | None, await self.session.scalar(statement))

    async def get_for_workflow(
        self, organization_id: UUID, workflow_run_id: UUID, *, lock: bool = False
    ) -> Approval | None:
        statement = select(Approval).where(
            Approval.organization_id == organization_id,
            Approval.workflow_run_id == workflow_run_id,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(Approval | None, await self.session.scalar(statement))

    async def list_queue(
        self, organization_id: UUID, *, limit: int, offset: int
    ) -> tuple[tuple[Approval, ...], int]:
        """Return only undecided active records in a stable oldest-first reviewer queue."""

        from sqlalchemy import func

        predicates = (
            Approval.organization_id == organization_id,
            Approval.status.in_(("pending", "assigned")),
            Approval.decision.is_(None),
        )
        total = await self.session.scalar(select(func.count(Approval.id)).where(*predicates))
        items = tuple(
            (
                await self.session.scalars(
                    select(Approval)
                    .where(*predicates)
                    .order_by(asc(Approval.inserted_at), asc(Approval.id))
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, int(total or 0)
