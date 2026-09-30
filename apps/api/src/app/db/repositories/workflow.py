"""Tenant-safe persistence for workflow-run records without orchestration logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.document import Document
from app.db.models.prompt import ModelUsageRecord
from app.db.models.workflow import (
    Approval,
    RetrievedSource,
    WorkflowNodeRun,
    WorkflowRun,
    WorkflowToolCall,
)
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

    async def add(self, workflow_run: WorkflowRun) -> WorkflowRun:
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

    async def add(self, node_run: WorkflowNodeRun) -> WorkflowNodeRun:
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


class WorkflowToolCallRepository:
    """Metadata-only tool calls scoped through a trusted parent workflow run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, tool_call: WorkflowToolCall) -> WorkflowToolCall:
        self.session.add(tool_call)
        return tool_call

    async def list_for_run(self, workflow_run_id: UUID) -> tuple[WorkflowToolCall, ...]:
        statement = (
            select(WorkflowToolCall)
            .where(WorkflowToolCall.workflow_run_id == workflow_run_id)
            .order_by(asc(WorkflowToolCall.started_at), asc(WorkflowToolCall.id))
        )
        return tuple((await self.session.scalars(statement)).all())


@dataclass(frozen=True)
class WorkflowTraceSourceRecord:
    """A governed source plus its current document record for a read-side policy check."""

    source: RetrievedSource
    document: Document | None


@dataclass(frozen=True)
class WorkflowTraceRecords:
    """Tenant-scoped persisted records needed to assemble one public workflow trace."""

    run: WorkflowRun
    nodes: tuple[WorkflowNodeRun, ...]
    tool_calls: tuple[WorkflowToolCall, ...]
    model_usage: tuple[ModelUsageRecord, ...]
    sources: tuple[WorkflowTraceSourceRecord, ...]


class WorkflowTraceRepository:
    """Load one trace only after binding every child query to a tenant-owned parent run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self, organization_id: UUID, workflow_run_id: UUID
    ) -> WorkflowTraceRecords | None:
        run = cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.id == workflow_run_id,
                )
            ),
        )
        if run is None:
            return None
        nodes = tuple(
            (
                await self.session.scalars(
                    select(WorkflowNodeRun)
                    .where(WorkflowNodeRun.workflow_run_id == run.id)
                    .order_by(asc(WorkflowNodeRun.started_at), asc(WorkflowNodeRun.id))
                )
            ).all()
        )
        tool_calls = tuple(
            (
                await self.session.scalars(
                    select(WorkflowToolCall)
                    .where(WorkflowToolCall.workflow_run_id == run.id)
                    .order_by(asc(WorkflowToolCall.started_at), asc(WorkflowToolCall.id))
                )
            ).all()
        )
        model_usage = tuple(
            (
                await self.session.scalars(
                    select(ModelUsageRecord)
                    .where(
                        ModelUsageRecord.organization_id == organization_id,
                        ModelUsageRecord.workflow_run_id == run.id,
                    )
                    .order_by(asc(ModelUsageRecord.inserted_at), asc(ModelUsageRecord.id))
                )
            ).all()
        )
        source_rows = (
            await self.session.execute(
                select(RetrievedSource, Document)
                .outerjoin(
                    Document,
                    (Document.id == RetrievedSource.document_id)
                    & (Document.organization_id == RetrievedSource.organization_id),
                )
                .where(
                    RetrievedSource.organization_id == organization_id,
                    RetrievedSource.workflow_run_id == run.id,
                )
                .order_by(asc(RetrievedSource.rank), asc(RetrievedSource.id))
            )
        ).all()
        sources = tuple(
            WorkflowTraceSourceRecord(source=row[0], document=row[1]) for row in source_rows
        )
        return WorkflowTraceRecords(
            run=run,
            nodes=nodes,
            tool_calls=tool_calls,
            model_usage=model_usage,
            sources=sources,
        )


class ApprovalRepository:
    """Tenant-scoped review persistence; authorization remains in the service layer."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, approval: Approval) -> Approval:
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
