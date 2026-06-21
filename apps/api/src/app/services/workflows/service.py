"""Internal workflow-run persistence service; no graph execution is implemented."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow import WorkflowNodeRun, WorkflowRun, WorkflowToolCall
from app.db.repositories.case import CaseRepository
from app.db.repositories.identity import UserRepository
from app.db.repositories.workflow import (
    WorkflowNodeRunRepository,
    WorkflowRunRepository,
    WorkflowToolCallRepository,
)
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


@dataclass(frozen=True)
class WorkflowToolCallCreate:
    """Trusted server-side metadata for a registered tool invocation only."""

    organization_id: UUID
    workflow_run_id: UUID
    workflow_node_run_id: UUID | None
    tool_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    retry_count: int
    input_summary: dict[str, object] = field(default_factory=dict)
    output_summary: dict[str, object] = field(default_factory=dict)
    error_summary: str | None = None


_CONTROLLED_CODE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_TOOL_STATUSES = frozenset({"succeeded", "failed", "rejected"})


class WorkflowRunService:
    """Verify scoped references before persisting a workflow run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WorkflowRunRepository(session)
        self.nodes = WorkflowNodeRunRepository(session)
        self.tool_calls = WorkflowToolCallRepository(session)
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

    async def claim_waiting_for_human_review(
        self, organization_id: UUID, workflow_run_id: UUID
    ) -> WorkflowRun | None:
        """Claim one persisted approval interruption exactly once for resumption."""

        async with self.session.begin_nested():
            run = await self.repository.get_for_update(organization_id, workflow_run_id)
            if run is None or run.status != "waiting_for_human_review":
                return None
            run.status = "running"
            await self.session.flush()
            return run

    async def pause(self, command: WorkflowRunFinalize) -> WorkflowRun | None:
        """Persist a non-terminal human-review checkpoint from a running graph run."""

        async with self.session.begin_nested():
            run = await self.repository.get_for_update(
                command.organization_id, command.workflow_run_id
            )
            if run is None or run.status != "running":
                return None
            if command.duration_ms < 0:
                raise ValueError("Workflow timing is invalid")
            run.status = "waiting_for_human_review"
            run.finished_at = None
            run.duration_ms = command.duration_ms
            run.state_snapshot = command.state_snapshot
            run.error_summary = None
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

    async def record_tool_call(self, command: WorkflowToolCallCreate) -> WorkflowToolCall:
        """Persist a bounded server-owned tool event under a tenant-owned workflow run."""

        run = await self.get_required(command.organization_id, command.workflow_run_id)
        if command.workflow_node_run_id is not None:
            node = await self.nodes.get_for_update(run.id, command.workflow_node_run_id)
            if node is None:
                raise NotFoundError("Workflow node")
        if command.duration_ms < 0 or command.retry_count < 0:
            raise ValueError("Tool timing is invalid")
        if command.status not in _TOOL_STATUSES or _TOOL_NAME.fullmatch(command.tool_name) is None:
            raise ValueError("Tool trace identity is invalid")
        error_code = _controlled_code(command.error_summary)
        if command.error_summary is not None and error_code is None:
            raise ValueError("Tool error code is invalid")
        tool_call = WorkflowToolCall(
            workflow_run_id=run.id,
            workflow_node_run_id=command.workflow_node_run_id,
            tool_name=command.tool_name,
            status=command.status,
            started_at=command.started_at,
            finished_at=command.finished_at,
            duration_ms=command.duration_ms,
            retry_count=command.retry_count,
            input_summary=_tool_summary(command.input_summary),
            output_summary=_tool_summary(command.output_summary),
            error_summary=error_code,
        )
        return await stage_write(
            self.session,
            lambda: self.tool_calls.create(tool_call),
            resource="Workflow tool call",
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


def _controlled_code(value: str | None) -> str | None:
    """Keep only compact controlled codes, never provider or exception text."""

    if value is None:
        return None
    return value if _CONTROLLED_CODE.fullmatch(value) is not None else None


def _tool_summary(value: dict[str, object]) -> dict[str, object]:
    """Store only a schema shape, so payloads and result bodies cannot persist here."""

    field_names = value.get("field_names")
    if not isinstance(field_names, (list, tuple)):
        return {}
    safe_names = [
        item
        for item in field_names[:32]
        if isinstance(item, str) and _TOOL_NAME.fullmatch(item) is not None
    ]
    return {"field_names": safe_names} if safe_names else {}
