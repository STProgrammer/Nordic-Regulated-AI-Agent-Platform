"""Closed start policy and durable persistence for the Phase-18 Evidence graph."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from agent_orchestrator.graphs.evidence_graph import EvidencePackage
from agent_orchestrator.graphs.evidence_types import EvidenceOutcome, EvidenceWorkflowState
from agent_orchestrator.types import WorkflowContext
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow import RetrievedSource, WorkflowRun
from app.db.repositories.case import CaseRepository, CaseUpdateValues
from app.services.audit.service import AuditEventCreate, AuditService
from app.services.auth.policy import (
    CaseAction,
    RetrievalAction,
    authorize_case_action,
    authorize_retrieval_action,
)
from app.services.auth.principal import Principal
from app.services.cases.policy import validate_case_transition
from app.services.common.persistence import stage_write
from app.services.errors import ConflictError, NotFoundError, WorkflowUnavailableError
from app.services.workflows.dispatch import WorkflowTaskDispatcher
from app.services.workflows.service import WorkflowRunCreate, WorkflowRunService

EVIDENCE_WORKFLOW_NAME = "evidence"
EVIDENCE_WORKFLOW_VERSION = "phase18-v1"


class EvidenceWorkflowService:
    """Own the closed Evidence start boundary; worker execution stays private."""

    def __init__(
        self, session: AsyncSession, *, dispatcher: WorkflowTaskDispatcher | None = None
    ) -> None:
        self.session = session
        self._workflows = WorkflowRunService(session)
        self._cases = CaseRepository(session)
        self._audit = AuditService(session)
        self._dispatcher = dispatcher

    async def start(self, principal: Principal, case_id: UUID) -> WorkflowRun:
        """Queue one server-owned Evidence run and publish only its UUID after commit."""

        authorize_case_action(principal, CaseAction.EDIT)
        authorize_retrieval_action(principal, RetrievalAction.SEARCH)
        case = await self._cases.get(principal.organization_id, case_id)
        if case is None:
            raise NotFoundError("Case")
        if case.status in {"archived", "approved", "rejected", "completed"}:
            raise ConflictError("Case")
        active = await self._active_run(principal.organization_id, case.id)
        if active is not None:
            raise ConflictError("Evidence workflow")
        if case.status in {"new", "needs_more_evidence", "failed"}:
            validate_case_transition(case.status, "processing")
            await self._cases.update(case, CaseUpdateValues(status="processing"))
        run = await self._workflows.create(
            WorkflowRunCreate(
                organization_id=principal.organization_id,
                case_id=case.id,
                started_by_user_id=principal.user_id,
                workflow_name=EVIDENCE_WORKFLOW_NAME,
                workflow_version=EVIDENCE_WORKFLOW_VERSION,
                status="queued",
                started_at=datetime.now(UTC),
                state_snapshot={
                    "workflow_name": EVIDENCE_WORKFLOW_NAME,
                    "workflow_version": EVIDENCE_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "queued",
                },
            )
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.evidence_queued",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case.id,
                event_data={"workflow": EVIDENCE_WORKFLOW_NAME, "status": "queued"},
            )
        )
        await self.session.commit()
        if self._dispatcher is not None:
            try:
                self._dispatcher.dispatch_evidence(run.id)
            except Exception as error:
                await self._mark_dispatch_failed(run, principal)
                raise WorkflowUnavailableError() from error
        return run

    async def _active_run(self, organization_id: UUID, case_id: UUID) -> WorkflowRun | None:
        return cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == EVIDENCE_WORKFLOW_NAME,
                    WorkflowRun.status.in_(("queued", "running")),
                )
                .order_by(desc(WorkflowRun.started_at), desc(WorkflowRun.id))
            ),
        )

    async def _mark_dispatch_failed(self, run: WorkflowRun, principal: Principal) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.duration_ms = 0
        run.error_summary = "dispatch_unavailable"
        run.state_snapshot = {
            "workflow_name": EVIDENCE_WORKFLOW_NAME,
            "workflow_version": EVIDENCE_WORKFLOW_VERSION,
            "state_schema_version": "v1",
            "status": "failed",
        }
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.evidence_failed",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data={
                    "workflow": EVIDENCE_WORKFLOW_NAME,
                    "status": "failed",
                    "reason_code": "dispatch_unavailable",
                },
            )
        )
        await self.session.commit()


async def persist_evidence_case_result(
    session: AsyncSession,
    context: WorkflowContext,
    state: EvidenceWorkflowState,
    package: EvidencePackage,
) -> None:
    """Persist source provenance and the narrow Needs More Evidence case transition atomically."""

    cases = CaseRepository(session)
    case = await cases.get(context.organization_id, context.case_id)
    if case is None:
        from agent_orchestrator.errors import ControlledWorkflowError

        raise ControlledWorkflowError("case_not_available")
    for source in package.sources:
        record = RetrievedSource(
            organization_id=context.organization_id,
            case_id=context.case_id,
            workflow_run_id=context.workflow_run_id,
            document_id=source.candidate.document_id,
            chunk_id=source.candidate.chunk_id,
            rank=source.candidate.rank,
            score=Decimal(str(source.candidate.rank_score)),
            retrieval_method=",".join(source.candidate.retrieval_methods),
            excerpt=source.excerpt,
            citation_label=source.citation_label,
        )
        await stage_write(session, _source_adder(session, record), resource="Evidence")
    if package.outcome is EvidenceOutcome.NEEDS_MORE_EVIDENCE and case.status == "processing":
        validate_case_transition(case.status, "needs_more_evidence")
        await stage_write(
            session,
            lambda: cases.update(case, CaseUpdateValues(status="needs_more_evidence")),
            resource="Case",
        )


async def _add_source(session: AsyncSession, source: RetrievedSource) -> RetrievedSource:
    session.add(source)
    return source


def _source_adder(
    session: AsyncSession, source: RetrievedSource
) -> Callable[[], Awaitable[RetrievedSource]]:
    async def add() -> RetrievedSource:
        return await _add_source(session, source)

    return add
