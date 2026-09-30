"""Closed Evidence-backed Extraction workflow policy, field reads, and bounded edits."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from agent_orchestrator.graphs.extraction_graph import ExtractionEvidenceSource
from agent_orchestrator.graphs.extraction_types import (
    ExtractionFieldKind,
    ExtractionValue,
    ExtractionWorkflowState,
    ValidatedExtractionField,
    serialized_value,
    validate_extraction_value,
)
from agent_orchestrator.types import WorkflowContext
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.workflow import ExtractedField, RetrievedSource, WorkflowRun
from app.db.repositories.case import CaseRepository
from app.db.repositories.extraction import ExtractedFieldRepository, ExtractedFieldWithDocument
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
from app.services.workflows.service import WorkflowRunInput, WorkflowRunService

EXTRACTION_WORKFLOW_NAME = "extraction"
EXTRACTION_WORKFLOW_VERSION = "phase19-v1"
EVIDENCE_WORKFLOW_NAME = "evidence"


@dataclass(frozen=True)
class EligibleEvidencePackage:
    workflow_run: WorkflowRun
    sources: tuple[ExtractionEvidenceSource, ...]


class ExtractionWorkflowService:
    """Own all public extraction operations; graph execution remains worker-only."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        confidence_threshold: float,
        dispatcher: WorkflowTaskDispatcher | None = None,
    ) -> None:
        self.session = session
        self._confidence_threshold = confidence_threshold
        self._workflows = WorkflowRunService(session)
        self._cases = CaseRepository(session)
        self._fields = ExtractedFieldRepository(session)
        self._audit = AuditService(session)
        self._dispatcher = dispatcher

    async def start(self, principal: Principal, case_id: UUID) -> WorkflowRun:
        """Add a queued run only when an eligible Evidence package exists."""

        authorize_case_action(principal, CaseAction.EDIT)
        authorize_retrieval_action(principal, RetrievalAction.SEARCH)
        case = await self._cases.get(principal.organization_id, case_id)
        if case is None:
            raise NotFoundError("Case")
        if case.status == "archived":
            raise NotFoundError("Case")
        if await self._active_run(principal.organization_id, case.id) is not None:
            raise ConflictError("Extraction workflow")
        evidence = await load_eligible_evidence(self.session, principal.organization_id, case.id)
        if evidence is None:
            return await self._record_needs_more_evidence(principal, case.id)
        run = await self._workflows.add(
            WorkflowRunInput(
                organization_id=principal.organization_id,
                case_id=case.id,
                started_by_user_id=principal.user_id,
                workflow_name=EXTRACTION_WORKFLOW_NAME,
                workflow_version=EXTRACTION_WORKFLOW_VERSION,
                status="queued",
                started_at=datetime.now(UTC),
                state_snapshot={
                    "workflow_name": EXTRACTION_WORKFLOW_NAME,
                    "workflow_version": EXTRACTION_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "queued",
                    "evidence_available": True,
                },
            )
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.extraction_queued",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case.id,
                event_data={"workflow": EXTRACTION_WORKFLOW_NAME, "status": "queued"},
            )
        )
        await self.session.commit()
        if self._dispatcher is not None:
            try:
                self._dispatcher.dispatch_extraction(run.id)
            except Exception as error:
                await self._mark_dispatch_failed(run, principal)
                raise WorkflowUnavailableError() from error
        return run

    async def list_fields(
        self, principal: Principal, case_id: UUID
    ) -> tuple[ExtractedFieldWithDocument, ...]:
        """Return fields from the latest completed extraction run only."""

        authorize_case_action(principal, CaseAction.READ)
        if await self._cases.get(principal.organization_id, case_id) is None:
            raise NotFoundError("Case")
        run = await self._latest_completed_run(principal.organization_id, case_id)
        if run is None:
            return ()
        return await self._fields.list_for_run(principal.organization_id, case_id, run.id)

    async def edit_field(
        self,
        principal: Principal,
        case_id: UUID,
        field_id: UUID,
        field_value: ExtractionValue,
    ) -> ExtractedFieldWithDocument:
        """Edit exactly one latest-run field through its original closed kind schema."""

        authorize_case_action(principal, CaseAction.EDIT)
        if await self._cases.get(principal.organization_id, case_id) is None:
            raise NotFoundError("Case")
        latest = await self._latest_completed_run(principal.organization_id, case_id)
        if latest is None:
            raise NotFoundError("Extracted field")
        field = await self._fields.get_for_update(
            principal.organization_id, case_id, latest.id, field_id
        )
        if field is None:
            raise NotFoundError("Extracted field")
        try:
            kind = ExtractionFieldKind(field.field_name)
        except ValueError as error:
            raise NotFoundError("Extracted field") from error
        parsed = validate_extraction_value(kind, serialized_value(field_value))
        field.field_value = serialized_value(parsed)
        field.human_edited = True
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.extraction_field_edited",
                resource_type="extracted_field",
                resource_id=field.id,
                case_id=case_id,
                event_data={
                    "workflow": EXTRACTION_WORKFLOW_NAME,
                    "field_kind": kind.value,
                    "human_edited": True,
                },
            )
        )
        await self.session.commit()
        views = await self._fields.list_for_run(principal.organization_id, case_id, latest.id)
        for view in views:
            if view.field.id == field.id:
                return view
        raise NotFoundError("Extracted field")

    async def _active_run(self, organization_id: UUID, case_id: UUID) -> WorkflowRun | None:
        return cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == EXTRACTION_WORKFLOW_NAME,
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
                    WorkflowRun.workflow_name == EXTRACTION_WORKFLOW_NAME,
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
                workflow_name=EXTRACTION_WORKFLOW_NAME,
                workflow_version=EXTRACTION_WORKFLOW_VERSION,
                status="needs_more_evidence",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                duration_ms=0,
                state_snapshot={
                    "workflow_name": EXTRACTION_WORKFLOW_NAME,
                    "workflow_version": EXTRACTION_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "needs_more_evidence",
                    "evidence_available": False,
                },
            )
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.extraction_needs_more_evidence",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case_id,
                event_data={
                    "workflow": EXTRACTION_WORKFLOW_NAME,
                    "status": "needs_more_evidence",
                    "evidence_available": False,
                },
            )
        )
        await self.session.commit()
        return run

    async def _mark_dispatch_failed(self, run: WorkflowRun, principal: Principal) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.duration_ms = 0
        run.error_summary = "dispatch_unavailable"
        run.state_snapshot = {
            "workflow_name": EXTRACTION_WORKFLOW_NAME,
            "workflow_version": EXTRACTION_WORKFLOW_VERSION,
            "state_schema_version": "v1",
            "status": "failed",
            "evidence_available": True,
        }
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.extraction_failed",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data={
                    "workflow": EXTRACTION_WORKFLOW_NAME,
                    "status": "failed",
                    "reason_code": "dispatch_unavailable",
                },
            )
        )
        await self.session.commit()


async def load_eligible_evidence(
    session: AsyncSession, organization_id: UUID, case_id: UUID
) -> EligibleEvidencePackage | None:
    """Load the latest current-governed Evidence package, never arbitrary source rows."""

    run = cast(
        WorkflowRun | None,
        await session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.case_id == case_id,
                WorkflowRun.workflow_name == EVIDENCE_WORKFLOW_NAME,
                WorkflowRun.status == "completed",
            )
            .order_by(desc(WorkflowRun.finished_at), desc(WorkflowRun.id))
        ),
    )
    if (
        run is None
        or run.state_snapshot.get("evidence_outcome") != "completed"
        or run.state_snapshot.get("evidence_sufficient") is not True
        or run.state_snapshot.get("contradiction_detected") is not False
    ):
        return None
    statement = (
        select(RetrievedSource)
        .join(
            Document,
            (Document.id == RetrievedSource.document_id)
            & (Document.organization_id == RetrievedSource.organization_id),
        )
        .where(
            RetrievedSource.organization_id == organization_id,
            RetrievedSource.case_id == case_id,
            RetrievedSource.workflow_run_id == run.id,
            Document.archived_at.is_(None),
            Document.source_status == "approved",
        )
        .order_by(RetrievedSource.rank.asc(), RetrievedSource.id.asc())
    )
    records = tuple((await session.scalars(statement)).all())
    if not records or len({record.citation_label for record in records}) != len(records):
        return None
    return EligibleEvidencePackage(
        workflow_run=run,
        sources=tuple(
            ExtractionEvidenceSource(
                citation_label=record.citation_label,
                chunk_id=record.chunk_id,
                excerpt=record.excerpt,
            )
            for record in records
        ),
    )


async def persist_extracted_fields(
    session: AsyncSession,
    context: WorkflowContext,
    state: ExtractionWorkflowState,
    fields: tuple[ValidatedExtractionField, ...],
) -> None:
    """Persist one immutable extraction run's validated, cited business fields."""

    repository = ExtractedFieldRepository(session)
    for field in fields:
        record = ExtractedField(
            organization_id=context.organization_id,
            case_id=context.case_id,
            workflow_run_id=context.workflow_run_id,
            field_name=field.kind.value,
            field_value=serialized_value(field.value),
            confidence=Decimal(str(field.confidence)),
            source_chunk_id=field.source_chunk_id,
            human_edited=False,
        )
        await stage_write(
            session,
            _field_adder(repository, record),
            resource="Extracted field",
        )


def _field_adder(
    repository: ExtractedFieldRepository, record: ExtractedField
) -> Callable[[], Awaitable[ExtractedField]]:
    async def add() -> ExtractedField:
        return await repository.add(record)

    return add
