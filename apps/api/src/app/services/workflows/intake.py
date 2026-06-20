"""Closed start/status/correction service for the Phase-17 Intake workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from agent_orchestrator.graphs.intake_types import IntakeCaseType, IntakeDomain
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow import WorkflowRun
from app.db.repositories.case import CaseRepository, CaseUpdateValues
from app.services.audit.service import AuditEventCreate, AuditService
from app.services.auth.policy import CaseAction, authorize_case_action
from app.services.auth.principal import Principal
from app.services.errors import ConflictError, NotFoundError, WorkflowUnavailableError
from app.services.workflows.dispatch import WorkflowTaskDispatcher
from app.services.workflows.service import WorkflowRunCreate, WorkflowRunService

INTAKE_WORKFLOW_NAME = "intake"
INTAKE_WORKFLOW_VERSION = "v1"


@dataclass(frozen=True)
class IntakeCorrection:
    """Closed user correction; no risk/prompt/provider/free-text control is accepted."""

    case_type: IntakeCaseType
    domain: IntakeDomain
    reason_code: str | None = None


class IntakeWorkflowService:
    """Own authenticated Intake workflow operations; graph execution stays worker-owned."""

    def __init__(
        self, session: AsyncSession, *, dispatcher: WorkflowTaskDispatcher | None = None
    ) -> None:
        """Compose scoped repositories around a caller-owned async transaction."""

        self.session = session
        self._workflows = WorkflowRunService(session)
        self._cases = CaseRepository(session)
        self._audit = AuditService(session)
        self._dispatcher = dispatcher

    async def start(self, principal: Principal, case_id: UUID) -> WorkflowRun:
        """Persist a queued closed Intake run and dispatch only its UUID after commit."""

        authorize_case_action(principal, CaseAction.EDIT)
        case = await self._cases.get(principal.organization_id, case_id)
        if case is None:
            raise NotFoundError("Case")
        run = await self._workflows.create(
            WorkflowRunCreate(
                organization_id=principal.organization_id,
                case_id=case.id,
                started_by_user_id=principal.user_id,
                workflow_name=INTAKE_WORKFLOW_NAME,
                workflow_version=INTAKE_WORKFLOW_VERSION,
                status="queued",
                started_at=datetime.now(UTC),
                state_snapshot={
                    "workflow_name": INTAKE_WORKFLOW_NAME,
                    "workflow_version": INTAKE_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "queued",
                },
            )
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.intake_queued",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case.id,
                event_data={"workflow": INTAKE_WORKFLOW_NAME, "status": "queued"},
            )
        )
        await self.session.commit()
        if self._dispatcher is not None:
            try:
                self._dispatcher.dispatch_intake(run.id)
            except Exception as error:
                await self._mark_dispatch_failed(run, principal)
                raise WorkflowUnavailableError() from error
        return run

    async def get_for_principal(self, principal: Principal, workflow_run_id: UUID) -> WorkflowRun:
        """Return only a current-tenant Intake run linked to a readable active case."""

        authorize_case_action(principal, CaseAction.READ)
        run = await self._workflows.get_required(principal.organization_id, workflow_run_id)
        if run.workflow_name != INTAKE_WORKFLOW_NAME:
            raise NotFoundError("Workflow run")
        if await self._cases.get(principal.organization_id, run.case_id) is None:
            raise NotFoundError("Workflow run")
        return run

    async def correct(
        self, principal: Principal, workflow_run_id: UUID, correction: IntakeCorrection
    ) -> WorkflowRun:
        """Atomically record a human classification correction on the latest low-confidence run."""

        authorize_case_action(principal, CaseAction.EDIT)
        run = await self.get_for_principal(principal, workflow_run_id)
        if run.status != "completed" or not bool(run.state_snapshot.get("low_confidence")):
            raise ConflictError("Intake workflow")
        latest = await self._latest_completed_intake(principal.organization_id, run.case_id)
        if latest is None or latest.id != run.id:
            raise ConflictError("Intake workflow")
        case = await self._cases.get(principal.organization_id, run.case_id)
        if case is None:
            raise NotFoundError("Workflow run")
        snapshot = dict(run.state_snapshot)
        snapshot["classification_source"] = "human_corrected"
        await self._cases.update(
            case,
            CaseUpdateValues(case_type=correction.case_type.value, domain=correction.domain.value),
        )
        run.state_snapshot = snapshot
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.intake_classification_corrected",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data={
                    "workflow": INTAKE_WORKFLOW_NAME,
                    "classification_source": "human_corrected",
                    "case_type": correction.case_type.value,
                    "domain": correction.domain.value,
                    **({"reason_code": correction.reason_code} if correction.reason_code else {}),
                },
            )
        )
        return run

    async def _latest_completed_intake(
        self, organization_id: UUID, case_id: UUID
    ) -> WorkflowRun | None:
        from sqlalchemy import desc, select

        return cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == INTAKE_WORKFLOW_NAME,
                    WorkflowRun.status == "completed",
                )
                .order_by(desc(WorkflowRun.finished_at), desc(WorkflowRun.id))
            ),
        )

    async def _mark_dispatch_failed(self, run: WorkflowRun, principal: Principal) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.duration_ms = 0
        run.error_summary = "dispatch_unavailable"
        run.state_snapshot = {
            "workflow_name": INTAKE_WORKFLOW_NAME,
            "workflow_version": INTAKE_WORKFLOW_VERSION,
            "state_schema_version": "v1",
            "status": "failed",
        }
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.intake_failed",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data={
                    "workflow": INTAKE_WORKFLOW_NAME,
                    "status": "failed",
                    "reason_code": "dispatch_unavailable",
                },
            )
        )
        await self.session.commit()
