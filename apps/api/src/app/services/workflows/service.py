"""Internal workflow-run persistence service; no graph execution is implemented."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow import WorkflowRun
from app.db.repositories.case import CaseRepository
from app.db.repositories.identity import UserRepository
from app.db.repositories.workflow import WorkflowRunRepository
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


class WorkflowRunService:
    """Verify scoped references before persisting a workflow run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WorkflowRunRepository(session)
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
