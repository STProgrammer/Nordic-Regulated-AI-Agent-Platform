"""Internal workflow-run persistence service; no graph execution is implemented."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow import WorkflowNodeRun, WorkflowRun
from app.db.repositories.case import CaseRepository
from app.db.repositories.identity import UserRepository
from app.db.repositories.workflow import WorkflowNodeRunRepository, WorkflowRunRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.common.querying import SortSpec
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class WorkflowRunCreate:
    """Typed persistence command for a future orchestrator-owned workflow run."""

    organization_id: UUID
    case_id: UUID
    started_by_user_id: UUID
    workflow_name: str
    workflow_version: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    total_cost_estimate: Decimal | None = None
    total_tokens: int | None = None
    error_summary: str | None = None
    state_snapshot: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowNodeStart:
    """Trusted, safe node-start data; content stays out of the trace."""

    organization_id: UUID
    workflow_run_id: UUID
    node_name: str
    started_at: datetime
    input_summary: dict[str, object]
    retry_count: int


@dataclass(frozen=True)
class WorkflowNodeFinish:
    """Trusted terminal node data with only controlled error codes."""

    organization_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    status: str
    finished_at: datetime
    duration_ms: int
    output_summary: dict[str, object]
    retry_count: int
    error_summary: str | None = None


@dataclass(frozen=True)
class WorkflowRunFinalize:
    """Trusted terminal run data used by the graph persistence adapter."""

    organization_id: UUID
    workflow_run_id: UUID
    status: str
    finished_at: datetime
    duration_ms: int
    state_snapshot: dict[str, object]
    error_summary: str | None = None


class WorkflowRunService:
    """Verify scoped references before persisting a workflow run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WorkflowRunRepository(session)
        self.nodes = WorkflowNodeRunRepository(session)
        self.cases = CaseRepository(session)
        self.users = UserRepository(session)

    async def create(self, command: WorkflowRunCreate) -> WorkflowRun:
        if await self.cases.get(command.organization_id, command.case_id) is None:
            raise NotFoundError("Case")
        if await self.users.get(command.organization_id, command.started_by_user_id) is None:
            raise NotFoundError("User")
        workflow_run = WorkflowRun(
            organization_id=command.organization_id,
            case_id=command.case_id,
            started_by_user_id=command.started_by_user_id,
            workflow_name=command.workflow_name,
            workflow_version=command.workflow_version,
            status=command.status,
            started_at=command.started_at,
            finished_at=command.finished_at,
            duration_ms=command.duration_ms,
            total_cost_estimate=command.total_cost_estimate,
            total_tokens=command.total_tokens,
            error_summary=command.error_summary,
            state_snapshot=command.state_snapshot,
        )
        return await stage_write(
            self.session,
            lambda: self.repository.create(workflow_run),
            resource="Workflow run",
        )

    async def get_required(self, organization_id: UUID, workflow_run_id: UUID) -> WorkflowRun:
        workflow_run = await self.repository.get(organization_id, workflow_run_id)
        if workflow_run is None:
            raise NotFoundError("Workflow run")
        return workflow_run

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
    ) -> Page[WorkflowRun]:
        return await self.repository.list(organization_id, pagination=pagination, sort=sort)

    async def claim_queued(
        self, organization_id: UUID, workflow_run_id: UUID
    ) -> WorkflowRun | None:
        """Move a queued run to running exactly once; duplicate broker delivery is a no-op."""

        async with self.session.begin_nested():
            run = await self.repository.get_for_update(organization_id, workflow_run_id)
            if run is None or run.status != "queued":
                return None
            run.status = "running"
            await self.session.flush()
            return run

    async def start_node(self, command: WorkflowNodeStart) -> WorkflowNodeRun:
        """Create one trace row after validating the tenant-owned parent run."""

        run = await self.get_required(command.organization_id, command.workflow_run_id)
        if run.status != "running":
            raise NotFoundError("Workflow run")
        if command.retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        node = WorkflowNodeRun(
            workflow_run_id=run.id,
            node_name=command.node_name,
            status="running",
            started_at=command.started_at,
            input_summary=command.input_summary,
            output_summary={},
            retry_count=command.retry_count,
        )
        return await stage_write(
            self.session, lambda: self.nodes.create(node), resource="Workflow node"
        )

    async def finish_node(self, command: WorkflowNodeFinish) -> WorkflowNodeRun:
        """Finalize a node only inside the parent tenant-owned workflow run."""

        run = await self.get_required(command.organization_id, command.workflow_run_id)
        node = await self.nodes.get_for_update(run.id, command.node_run_id)
        if node is None or node.status != "running":
            raise NotFoundError("Workflow node")
        if command.duration_ms < 0 or command.retry_count < 0:
            raise ValueError("Node timing is invalid")
        return await self.nodes.finish(
            node,
            status=command.status,
            finished_at=command.finished_at,
            duration_ms=command.duration_ms,
            output_summary=command.output_summary,
            retry_count=command.retry_count,
            error_summary=command.error_summary,
        )

    async def finalize(self, command: WorkflowRunFinalize) -> WorkflowRun | None:
        """Persist a terminal safe snapshot only from a running tenant-owned run."""

        async with self.session.begin_nested():
            run = await self.repository.get_for_update(
                command.organization_id, command.workflow_run_id
            )
            if run is None or run.status != "running":
                return None
            if command.duration_ms < 0:
                raise ValueError("Workflow timing is invalid")
            run.status = command.status
            run.finished_at = command.finished_at
            run.duration_ms = command.duration_ms
            run.state_snapshot = command.state_snapshot
            run.error_summary = command.error_summary
            await self.session.flush()
            return run
