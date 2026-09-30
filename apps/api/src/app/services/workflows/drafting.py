"""Closed Evidence-backed Drafting workflow policy and original-draft reads."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from agent_orchestrator.graphs.drafting_graph import ValidatedDraft
from agent_orchestrator.graphs.drafting_types import DraftingWorkflowState, OutputLanguage
from agent_orchestrator.types import WorkflowContext
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow import AgentMessage, RetrievedSource, WorkflowRun
from app.db.repositories.case import CaseRepository
from app.services.audit.service import AuditEventInput, AuditService
from app.services.auth.policy import (
    CaseAction,
    RetrievalAction,
    authorize_case_action,
    authorize_retrieval_action,
)
from app.services.auth.principal import Principal
from app.services.common.persistence import stage_write
from app.services.errors import ConflictError, NotFoundError, WorkflowUnavailableError
from app.services.workflows.dispatch import WorkflowTaskDispatcher
from app.services.workflows.extraction import load_eligible_evidence
from app.services.workflows.service import WorkflowRunInput, WorkflowRunService

DRAFTING_WORKFLOW_NAME = "drafting"
DRAFTING_WORKFLOW_VERSION = "phase24-v1"


@dataclass(frozen=True)
class DraftRecord:
    """Protected original text and deliberately small source presentation metadata."""

    message: AgentMessage
    sources: tuple[RetrievedSource, ...]


class DraftingWorkflowService:
    """Own closed Drafting lifecycle/read operations; graph execution is worker-only."""

    def __init__(
        self, session: AsyncSession, *, dispatcher: WorkflowTaskDispatcher | None = None
    ) -> None:
        self.session = session
        self._workflows = WorkflowRunService(session)
        self._cases = CaseRepository(session)
        self._audit = AuditService(session)
        self._dispatcher = dispatcher

    async def start(
        self, principal: Principal, case_id: UUID, output_language: OutputLanguage | None = None
    ) -> WorkflowRun:
        """Queue one Drafting run from the latest eligible Evidence package only."""

        authorize_case_action(principal, CaseAction.EDIT)
        authorize_retrieval_action(principal, RetrievalAction.ANSWER)
        case = await self._cases.get(principal.organization_id, case_id)
        if case is None or case.status == "archived":
            raise NotFoundError("Case")
        if await self._active_run(principal.organization_id, case.id) is not None:
            raise ConflictError("Drafting workflow")
        if await load_eligible_evidence(self.session, principal.organization_id, case.id) is None:
            return await self._record_needs_more_evidence(principal, case.id)

        language = output_language or OutputLanguage(case.language)
        run = await self._workflows.add(
            WorkflowRunInput(
                organization_id=principal.organization_id,
                case_id=case.id,
                started_by_user_id=principal.user_id,
                workflow_name=DRAFTING_WORKFLOW_NAME,
                workflow_version=DRAFTING_WORKFLOW_VERSION,
                status="queued",
                started_at=datetime.now(UTC),
                state_snapshot={
                    "workflow_name": DRAFTING_WORKFLOW_NAME,
                    "workflow_version": DRAFTING_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "queued",
                    "target_language": language.value,
                    "language_explicit": output_language is not None,
                    "evidence_available": True,
                    "draft_available": False,
                },
            )
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.drafting_queued",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case.id,
                event_data={
                    "workflow": DRAFTING_WORKFLOW_NAME,
                    "status": "queued",
                    "target_language": language.value,
                    "language_explicit": output_language is not None,
                },
            )
        )
        await self.session.commit()
        if self._dispatcher is not None:
            try:
                self._dispatcher.dispatch_drafting(run.id)
            except Exception as error:
                await self._mark_dispatch_failed(run, principal, language)
                raise WorkflowUnavailableError() from error
        return run

    async def get_draft(self, principal: Principal, case_id: UUID) -> DraftRecord:
        """Return only the latest completed original draft for an authorized case reader."""

        authorize_case_action(principal, CaseAction.READ)
        if await self._cases.get(principal.organization_id, case_id) is None:
            raise NotFoundError("Case")
        run = await self._latest_completed_run(principal.organization_id, case_id)
        if run is None:
            raise NotFoundError("Draft")
        message = cast(
            AgentMessage | None,
            await self.session.scalar(
                select(AgentMessage)
                .where(
                    AgentMessage.organization_id == principal.organization_id,
                    AgentMessage.case_id == case_id,
                    AgentMessage.workflow_run_id == run.id,
                    AgentMessage.message_type == "draft",
                )
                .order_by(desc(AgentMessage.inserted_at), desc(AgentMessage.id))
            ),
        )
        if message is None:
            raise NotFoundError("Draft")
        sources = tuple(
            (
                await self.session.scalars(
                    select(RetrievedSource)
                    .where(
                        RetrievedSource.organization_id == principal.organization_id,
                        RetrievedSource.case_id == case_id,
                        RetrievedSource.workflow_run_id == run.id,
                    )
                    .order_by(RetrievedSource.rank.asc(), RetrievedSource.id.asc())
                )
            ).all()
        )
        return DraftRecord(message=message, sources=sources)

    async def _active_run(self, organization_id: UUID, case_id: UUID) -> WorkflowRun | None:
        return cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == DRAFTING_WORKFLOW_NAME,
                    WorkflowRun.status.in_(("queued", "running")),
                )
                .order_by(desc(WorkflowRun.started_at), desc(WorkflowRun.id))
            ),
        )

    async def _latest_completed_run(
        self, organization_id: UUID, case_id: UUID
    ) -> WorkflowRun | None:
        return cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == DRAFTING_WORKFLOW_NAME,
                    WorkflowRun.status == "completed",
                )
                .order_by(desc(WorkflowRun.finished_at), desc(WorkflowRun.id))
            ),
        )

    async def _record_needs_more_evidence(self, principal: Principal, case_id: UUID) -> WorkflowRun:
        run = await self._workflows.add(
            WorkflowRunInput(
                organization_id=principal.organization_id,
                case_id=case_id,
                started_by_user_id=principal.user_id,
                workflow_name=DRAFTING_WORKFLOW_NAME,
                workflow_version=DRAFTING_WORKFLOW_VERSION,
                status="needs_more_evidence",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                duration_ms=0,
                state_snapshot={
                    "workflow_name": DRAFTING_WORKFLOW_NAME,
                    "workflow_version": DRAFTING_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "needs_more_evidence",
                    "evidence_available": False,
                    "draft_available": False,
                },
            )
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.drafting_needs_more_evidence",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case_id,
                event_data={
                    "workflow": DRAFTING_WORKFLOW_NAME,
                    "status": "needs_more_evidence",
                    "evidence_available": False,
                },
            )
        )
        await self.session.commit()
        return run

    async def _mark_dispatch_failed(
        self, run: WorkflowRun, principal: Principal, language: OutputLanguage
    ) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.duration_ms = 0
        run.error_summary = "dispatch_unavailable"
        run.state_snapshot = {
            "workflow_name": DRAFTING_WORKFLOW_NAME,
            "workflow_version": DRAFTING_WORKFLOW_VERSION,
            "state_schema_version": "v1",
            "status": "failed",
            "target_language": language.value,
            "evidence_available": True,
            "draft_available": False,
        }
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.drafting_failed",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data={
                    "workflow": DRAFTING_WORKFLOW_NAME,
                    "status": "failed",
                    "reason_code": "dispatch_unavailable",
                },
            )
        )
        await self.session.commit()


async def persist_draft(
    session: AsyncSession,
    context: WorkflowContext,
    state: DraftingWorkflowState,
    draft: ValidatedDraft,
) -> None:
    """Persist exactly one validated original draft and same-run source provenance."""

    evidence = await load_eligible_evidence(session, context.organization_id, context.case_id)
    if evidence is None:
        from agent_orchestrator.errors import ControlledWorkflowError

        raise ControlledWorkflowError("eligible_evidence_unavailable")
    source_rows = tuple(
        (
            await session.scalars(
                select(RetrievedSource)
                .where(
                    RetrievedSource.organization_id == context.organization_id,
                    RetrievedSource.workflow_run_id == evidence.workflow_run.id,
                )
                .order_by(RetrievedSource.rank.asc(), RetrievedSource.id.asc())
            )
        ).all()
    )
    if not source_rows:
        from agent_orchestrator.errors import ControlledWorkflowError

        raise ControlledWorkflowError("eligible_evidence_unavailable")
    for source in source_rows:
        record = RetrievedSource(
            organization_id=context.organization_id,
            case_id=context.case_id,
            workflow_run_id=context.workflow_run_id,
            document_id=source.document_id,
            chunk_id=source.chunk_id,
            rank=source.rank,
            score=source.score,
            retrieval_method=source.retrieval_method,
            excerpt=source.excerpt,
            citation_label=source.citation_label,
        )
        await stage_write(session, _source_write(session, record), resource="Draft source")
    message = AgentMessage(
        organization_id=context.organization_id,
        case_id=context.case_id,
        workflow_run_id=context.workflow_run_id,
        message_type="draft",
        role="assistant",
        content=draft.content,
        structured_output={
            "language": draft.language.value,
            "draft_kind": state.draft_kind.value,
            "citation_labels": list(draft.citation_labels),
        },
        model_provider=draft.usage.provider,
        model_name=draft.usage.model_name,
        prompt_version_id=draft.prompt.prompt_id,
        token_input=draft.usage.token_input,
        token_output=draft.usage.token_output,
        cost_estimate=None,
        latency_ms=draft.usage.latency_ms,
    )
    await stage_write(session, _message_write(session, message), resource="Draft")


async def _add_source(session: AsyncSession, record: RetrievedSource) -> RetrievedSource:
    session.add(record)
    return record


async def _add_message(session: AsyncSession, message: AgentMessage) -> AgentMessage:
    session.add(message)
    return message


def _source_write(
    session: AsyncSession, record: RetrievedSource
) -> Callable[[], Awaitable[RetrievedSource]]:
    async def write() -> RetrievedSource:
        return await _add_source(session, record)

    return write


def _message_write(
    session: AsyncSession, message: AgentMessage
) -> Callable[[], Awaitable[AgentMessage]]:
    async def write() -> AgentMessage:
        return await _add_message(session, message)

    return write
