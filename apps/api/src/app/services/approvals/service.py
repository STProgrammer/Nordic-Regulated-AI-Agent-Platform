"""Tenant-safe human approval lifecycle, review packets, and reviewer policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.graphs.approval_types import ApprovalLifecycle, ReviewerDecision
from agent_orchestrator.types import WorkflowContext
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import get_telemetry
from app.db.models.case import Case
from app.db.models.document import Document
from app.db.models.identity import Role, User, UserRole
from app.db.models.workflow import (
    AgentMessage,
    Approval,
    ExtractedField,
    RetrievedSource,
    RiskAssessment,
    WorkflowRun,
)
from app.db.repositories.case import CaseRepository
from app.db.repositories.workflow import ApprovalRepository
from app.services.audit.service import AuditEventInput, AuditService
from app.services.auth.policy import ApprovalAuthorizationInput, authorize_approval, ensure_roles
from app.services.auth.principal import Principal, RoleName
from app.services.cases.policy import validate_case_transition
from app.services.common.persistence import stage_write
from app.services.errors import (
    AuthorizationDeniedError,
    ConflictError,
    NotFoundError,
    WorkflowUnavailableError,
)
from app.services.workflows.dispatch import WorkflowTaskDispatcher
from app.services.workflows.service import WorkflowRunInput, WorkflowRunService

APPROVAL_WORKFLOW_NAME = "human_approval"
APPROVAL_WORKFLOW_VERSION = "phase22-v1"
_DRAFTING_WORKFLOW_NAME = "drafting"
_EXTRACTION_WORKFLOW_NAME = "extraction"
_RISK_WORKFLOW_NAME = "risk_compliance"
_ACTIVE_APPROVAL_STATUSES = frozenset({"pending", "assigned"})
_APPROVAL_ROLE_NAMES = frozenset({RoleName.ADMIN.value, RoleName.COMPLIANCE_REVIEWER.value})


@dataclass(frozen=True)
class ApprovalQueueItem:
    approval: Approval
    case: Case


@dataclass(frozen=True)
class ApprovalSourceReference:
    citation_label: str
    document_id: UUID
    chunk_id: UUID


@dataclass(frozen=True)
class ApprovalExtractedField:
    field_id: UUID
    field_kind: str
    field_value: dict[str, object]
    source_document_id: UUID | None
    source_chunk_id: UUID | None
    human_edited: bool


@dataclass(frozen=True)
class ApprovalReviewPacket:
    approval: Approval
    case: Case
    risk: RiskAssessment
    sources: tuple[ApprovalSourceReference, ...]
    extracted_fields: tuple[ApprovalExtractedField, ...]
    workflow_status: str


@dataclass(frozen=True)
class ApprovalActionSubmission:
    approval: Approval
    workflow_status: str


class ApprovalWorkflowService:
    """Own all reviewer state changes; routes never patch approval/case rows directly."""

    def __init__(
        self, session: AsyncSession, *, dispatcher: WorkflowTaskDispatcher | None = None
    ) -> None:
        self.session = session
        self._approvals = ApprovalRepository(session)
        self._cases = CaseRepository(session)
        self._workflows = WorkflowRunService(session)
        self._audit = AuditService(session)
        self._dispatcher = dispatcher

    async def add_required_run(self, risk_context: WorkflowContext) -> WorkflowRun | None:
        """Add one server-selected review run after the exact completed risk run requires it."""

        assessment = cast(
            RiskAssessment | None,
            await self.session.scalar(
                select(RiskAssessment).where(
                    RiskAssessment.organization_id == risk_context.organization_id,
                    RiskAssessment.case_id == risk_context.case_id,
                    RiskAssessment.workflow_run_id == risk_context.workflow_run_id,
                    RiskAssessment.requires_approval.is_(True),
                )
            ),
        )
        if assessment is None:
            return None
        existing = cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == risk_context.organization_id,
                    WorkflowRun.case_id == risk_context.case_id,
                    WorkflowRun.workflow_name == APPROVAL_WORKFLOW_NAME,
                    WorkflowRun.status.in_(("queued", "running", "waiting_for_human_review")),
                )
                .order_by(desc(WorkflowRun.started_at), desc(WorkflowRun.id))
            ),
        )
        if existing is not None:
            return existing
        run = await self._workflows.add(
            WorkflowRunInput(
                organization_id=risk_context.organization_id,
                case_id=risk_context.case_id,
                started_by_user_id=risk_context.initiated_by_user_id,
                workflow_name=APPROVAL_WORKFLOW_NAME,
                workflow_version=APPROVAL_WORKFLOW_VERSION,
                status="queued",
                started_at=datetime.now(UTC),
                state_snapshot={
                    "workflow_name": APPROVAL_WORKFLOW_NAME,
                    "workflow_version": APPROVAL_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "queued",
                    "approval_required": True,
                },
            )
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=risk_context.organization_id,
                actor_user_id=risk_context.initiated_by_user_id,
                event_type="approval.workflow_queued",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=risk_context.case_id,
                event_data={"workflow": APPROVAL_WORKFLOW_NAME, "status": "queued"},
            )
        )
        return run

    async def prepare_review_packet(self, context: WorkflowContext) -> UUID:
        """Pin one immutable source-grounded draft and current required risk result to this run."""

        existing = await self._approvals.get_for_workflow(
            context.organization_id, context.workflow_run_id
        )
        if existing is not None:
            return existing.id
        inputs = await self._eligible_inputs(context.organization_id, context.case_id)
        if inputs is None:
            raise ControlledWorkflowError("approval_prerequisites_unavailable")
        case, risk, draft_run, draft_message, source_count = inputs
        if source_count == 0:
            raise ControlledWorkflowError("approval_provenance_unavailable")
        approval = Approval(
            organization_id=context.organization_id,
            case_id=context.case_id,
            workflow_run_id=context.workflow_run_id,
            drafting_workflow_run_id=draft_run.id,
            risk_assessment_id=risk.id,
            status=ApprovalLifecycle.PENDING.value,
            ai_draft=draft_message.content,
        )
        await stage_write(
            self.session,
            lambda: self._approvals.add(approval),
            resource="Approval",
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=context.organization_id,
                actor_user_id=context.initiated_by_user_id,
                event_type="approval.review_packet_created",
                resource_type="approval",
                resource_id=approval.id,
                case_id=case.id,
                event_data={
                    "workflow": APPROVAL_WORKFLOW_NAME,
                    "status": ApprovalLifecycle.PENDING.value,
                    "risk_level": risk.risk_level,
                },
            )
        )
        return approval.id

    async def mark_interrupted(self, context: WorkflowContext, approval_id: UUID) -> None:
        """Move only a valid required-review case to its durable human-review boundary."""

        async with self.session.begin_nested():
            approval = await self._approvals.get_for_update(context.organization_id, approval_id)
            case = await self._locked_case(context.organization_id, context.case_id)
            if (
                approval is None
                or case is None
                or approval.workflow_run_id != context.workflow_run_id
            ):
                raise ControlledWorkflowError("approval_packet_unavailable")
            if case.status == "waiting_for_human_review":
                return
            # Earlier workflow phases intentionally leave a submitted case in
            # ``new``. Reaching this checkpoint proves server-owned work ran, so
            # advance through the established lifecycle before reserving review.
            if case.status == "new":
                validate_case_transition(case.status, "processing")
                case.status = "processing"
            if case.status != "processing":
                raise ControlledWorkflowError("case_not_ready_for_review")
            validate_case_transition(case.status, "waiting_for_human_review")
            case.status = "waiting_for_human_review"
            approval.interrupted_at = approval.interrupted_at or datetime.now(UTC)
            await self.session.flush()
        await self._audit.record_event(
            AuditEventInput(
                organization_id=context.organization_id,
                actor_user_id=context.initiated_by_user_id,
                event_type="approval.interrupted_for_human_review",
                resource_type="approval",
                resource_id=approval_id,
                case_id=context.case_id,
                event_data={
                    "workflow": APPROVAL_WORKFLOW_NAME,
                    "status": "waiting_for_human_review",
                },
            )
        )

    async def list_queue(
        self, principal: Principal, *, limit: int, offset: int
    ) -> tuple[tuple[ApprovalQueueItem, ...], int]:
        self._ensure_approval_viewer(principal)
        approvals, total = await self._approvals.list_queue(
            principal.organization_id, limit=limit, offset=offset
        )
        items: list[ApprovalQueueItem] = []
        for approval in approvals:
            case = await self._cases.get(principal.organization_id, approval.case_id)
            if case is not None:
                items.append(ApprovalQueueItem(approval=approval, case=case))
        return tuple(items), total

    async def get_review_packet(
        self, principal: Principal, approval_id: UUID
    ) -> ApprovalReviewPacket:
        self._ensure_approval_viewer(principal)
        approval = await self._approvals.get(principal.organization_id, approval_id)
        if approval is None:
            raise NotFoundError("Approval")
        case = await self._cases.get(principal.organization_id, approval.case_id)
        if case is None or approval.risk_assessment_id is None:
            raise NotFoundError("Approval")
        risk = cast(
            RiskAssessment | None,
            await self.session.scalar(
                select(RiskAssessment).where(
                    RiskAssessment.id == approval.risk_assessment_id,
                    RiskAssessment.organization_id == principal.organization_id,
                    RiskAssessment.case_id == approval.case_id,
                    RiskAssessment.requires_approval.is_(True),
                )
            ),
        )
        if risk is None or approval.ai_draft is None:
            raise NotFoundError("Approval")
        sources = await self._approval_sources(principal.organization_id, approval)
        fields = await self._latest_extracted_fields(principal.organization_id, approval.case_id)
        run = await self._workflows.get_required(
            principal.organization_id, approval.workflow_run_id
        )
        return ApprovalReviewPacket(
            approval=approval,
            case=case,
            risk=risk,
            sources=sources,
            extracted_fields=fields,
            workflow_status=run.status,
        )

    async def submit_decision(
        self,
        principal: Principal,
        approval_id: UUID,
        *,
        decision: ReviewerDecision,
        reviewer_comment: str | None,
        final_text: str | None = None,
    ) -> ApprovalActionSubmission:
        """Persist exactly one validated decision, then dispatch only its workflow UUID."""

        if decision is ReviewerDecision.EDIT_AND_APPROVE and final_text is None:
            raise ConflictError("Approval decision")
        if decision is not ReviewerDecision.EDIT_AND_APPROVE and final_text is not None:
            raise ConflictError("Approval decision")
        async with self.session.begin_nested():
            approval = await self._approvals.get_for_update(principal.organization_id, approval_id)
            if approval is None:
                raise NotFoundError("Approval")
            case = await self._locked_case(principal.organization_id, approval.case_id)
            risk = await self._risk_for_approval(principal.organization_id, approval)
            if case is None or risk is None:
                raise NotFoundError("Approval")
            self._authorize_decision(principal, approval, case, risk)
            if approval.status not in _ACTIVE_APPROVAL_STATUSES or approval.decision is not None:
                raise ConflictError("Approval")
            if (
                approval.assigned_user_id is not None
                and approval.assigned_user_id != principal.user_id
            ):
                raise AuthorizationDeniedError()
            if case.status != "waiting_for_human_review":
                raise ConflictError("Approval")
            approval.assigned_user_id = approval.assigned_user_id or principal.user_id
            approval.status = ApprovalLifecycle.ASSIGNED.value
            approval.reviewer_user_id = principal.user_id
            approval.decision = decision.value
            approval.reviewer_comment = reviewer_comment
            approval.final_text = final_text
            approval.decision_at = datetime.now(UTC)
            await self.session.flush()
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="approval.decision_submitted",
                resource_type="approval",
                resource_id=approval_id,
                case_id=approval.case_id,
                event_data={"decision": decision.value, "workflow": APPROVAL_WORKFLOW_NAME},
            )
        )
        with get_telemetry().span("approval.decision", {"approval.decision": decision.value}):
            await self.session.commit()
        get_telemetry().approval_decision(decision=decision.value)
        if self._dispatcher is not None:
            try:
                self._dispatcher.dispatch_human_approval(approval.workflow_run_id)
            except Exception as error:
                raise WorkflowUnavailableError() from error
        run = await self._workflows.get_required(
            principal.organization_id, approval.workflow_run_id
        )
        return ApprovalActionSubmission(approval=approval, workflow_status=run.status)

    async def reassign(
        self, principal: Principal, approval_id: UUID, *, assigned_user_id: UUID
    ) -> Approval:
        """Assign a still-pending review only to an active approval-capable tenant user."""

        self._ensure_approval_viewer(principal)
        async with self.session.begin_nested():
            approval = await self._approvals.get_for_update(principal.organization_id, approval_id)
            if approval is None:
                raise NotFoundError("Approval")
            if approval.status not in _ACTIVE_APPROVAL_STATUSES or approval.decision is not None:
                raise ConflictError("Approval")
            if not await self._is_active_approval_reviewer(
                principal.organization_id, assigned_user_id
            ):
                raise NotFoundError("User")
            approval.assigned_user_id = assigned_user_id
            approval.status = ApprovalLifecycle.ASSIGNED.value
            await self.session.flush()
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="approval.reassigned",
                resource_type="approval",
                resource_id=approval_id,
                case_id=approval.case_id,
                event_data={"workflow": APPROVAL_WORKFLOW_NAME, "status": "assigned"},
            )
        )
        return approval

    async def load_decision(
        self, context: WorkflowContext, approval_id: UUID
    ) -> ReviewerDecision | None:
        approval = await self._approvals.get_for_workflow(
            context.organization_id, context.workflow_run_id
        )
        if approval is None or approval.id != approval_id or approval.decision is None:
            return None
        try:
            return ReviewerDecision(approval.decision)
        except ValueError:
            return None

    async def resolve_decision(
        self, context: WorkflowContext, approval_id: UUID, decision: ReviewerDecision
    ) -> None:
        """Atomically resolve approval, case, and audit state during the UUID-only resume task."""

        async with self.session.begin_nested():
            approval = await self._approvals.get_for_update(context.organization_id, approval_id)
            case = await self._locked_case(context.organization_id, context.case_id)
            if (
                approval is None
                or case is None
                or approval.workflow_run_id != context.workflow_run_id
                or approval.decision != decision.value
                or approval.reviewer_user_id is None
                or approval.status not in _ACTIVE_APPROVAL_STATUSES
                or case.status != "waiting_for_human_review"
            ):
                raise ControlledWorkflowError("approval_resolution_unavailable")
            target_status = _case_status_for_decision(decision)
            validate_case_transition(case.status, target_status)
            approval.status = _lifecycle_for_decision(decision).value
            approval.resumed_at = datetime.now(UTC)
            case.status = target_status
            await self.session.flush()
        await self._audit.record_event(
            AuditEventInput(
                organization_id=context.organization_id,
                actor_user_id=approval.reviewer_user_id,
                event_type="approval.workflow_resumed",
                resource_type="approval",
                resource_id=approval.id,
                case_id=context.case_id,
                event_data={"decision": decision.value, "workflow": APPROVAL_WORKFLOW_NAME},
            )
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=context.organization_id,
                actor_user_id=approval.reviewer_user_id,
                event_type=f"approval.{_lifecycle_for_decision(decision).value}",
                resource_type="approval",
                resource_id=approval.id,
                case_id=context.case_id,
                event_data={
                    "decision": decision.value,
                    "case_status": _case_status_for_decision(decision),
                },
            )
        )

    async def approval_for_workflow(
        self, organization_id: UUID, workflow_run_id: UUID
    ) -> Approval | None:
        return await self._approvals.get_for_workflow(organization_id, workflow_run_id)

    async def _eligible_inputs(
        self, organization_id: UUID, case_id: UUID
    ) -> tuple[Case, RiskAssessment, WorkflowRun, AgentMessage, int] | None:
        case = await self._cases.get(organization_id, case_id)
        if case is None or case.status == "archived":
            return None
        risk = cast(
            RiskAssessment | None,
            await self.session.scalar(
                select(RiskAssessment)
                .join(
                    WorkflowRun,
                    (WorkflowRun.id == RiskAssessment.workflow_run_id)
                    & (WorkflowRun.organization_id == RiskAssessment.organization_id),
                )
                .where(
                    RiskAssessment.organization_id == organization_id,
                    RiskAssessment.case_id == case_id,
                    RiskAssessment.requires_approval.is_(True),
                    WorkflowRun.workflow_name == _RISK_WORKFLOW_NAME,
                    WorkflowRun.status == "completed",
                )
                .order_by(desc(RiskAssessment.inserted_at), desc(RiskAssessment.id))
            ),
        )
        if risk is None:
            return None
        draft_run = cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == _DRAFTING_WORKFLOW_NAME,
                    WorkflowRun.status == "completed",
                )
                .order_by(desc(WorkflowRun.finished_at), desc(WorkflowRun.id))
            ),
        )
        if draft_run is None or draft_run.state_snapshot.get("draft_available") is not True:
            return None
        message = cast(
            AgentMessage | None,
            await self.session.scalar(
                select(AgentMessage)
                .where(
                    AgentMessage.organization_id == organization_id,
                    AgentMessage.case_id == case_id,
                    AgentMessage.workflow_run_id == draft_run.id,
                    AgentMessage.message_type == "draft",
                    AgentMessage.role == "assistant",
                )
                .order_by(desc(AgentMessage.inserted_at), desc(AgentMessage.id))
            ),
        )
        if message is None:
            return None
        source_count = int(
            await self.session.scalar(
                select(func.count(RetrievedSource.id))
                .join(
                    Document,
                    (Document.id == RetrievedSource.document_id)
                    & (Document.organization_id == RetrievedSource.organization_id),
                )
                .where(
                    RetrievedSource.organization_id == organization_id,
                    RetrievedSource.case_id == case_id,
                    RetrievedSource.workflow_run_id == draft_run.id,
                    Document.source_status == "approved",
                    Document.archived_at.is_(None),
                )
            )
            or 0
        )
        return case, risk, draft_run, message, source_count

    async def _approval_sources(
        self, organization_id: UUID, approval: Approval
    ) -> tuple[ApprovalSourceReference, ...]:
        if approval.drafting_workflow_run_id is None:
            return ()
        rows = (
            await self.session.execute(
                select(
                    RetrievedSource.citation_label,
                    RetrievedSource.document_id,
                    RetrievedSource.chunk_id,
                )
                .join(
                    Document,
                    (Document.id == RetrievedSource.document_id)
                    & (Document.organization_id == RetrievedSource.organization_id),
                )
                .where(
                    RetrievedSource.organization_id == organization_id,
                    RetrievedSource.case_id == approval.case_id,
                    RetrievedSource.workflow_run_id == approval.drafting_workflow_run_id,
                    Document.source_status == "approved",
                    Document.archived_at.is_(None),
                )
                .order_by(RetrievedSource.rank.asc(), RetrievedSource.id.asc())
            )
        ).all()
        return tuple(
            ApprovalSourceReference(
                citation_label=row.citation_label,
                document_id=row.document_id,
                chunk_id=row.chunk_id,
            )
            for row in rows
        )

    async def _latest_extracted_fields(
        self, organization_id: UUID, case_id: UUID
    ) -> tuple[ApprovalExtractedField, ...]:
        run = cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == _EXTRACTION_WORKFLOW_NAME,
                    WorkflowRun.status == "completed",
                )
                .order_by(desc(WorkflowRun.finished_at), desc(WorkflowRun.id))
            ),
        )
        if run is None:
            return ()
        fields = tuple(
            (
                await self.session.scalars(
                    select(ExtractedField)
                    .where(
                        ExtractedField.organization_id == organization_id,
                        ExtractedField.case_id == case_id,
                        ExtractedField.workflow_run_id == run.id,
                    )
                    .order_by(ExtractedField.inserted_at.asc(), ExtractedField.id.asc())
                )
            ).all()
        )
        return tuple(
            ApprovalExtractedField(
                field_id=field.id,
                field_kind=field.field_name,
                field_value=field.field_value,
                source_document_id=None,
                source_chunk_id=field.source_chunk_id,
                human_edited=field.human_edited,
            )
            for field in fields
        )

    async def _locked_case(self, organization_id: UUID, case_id: UUID) -> Case | None:
        return cast(
            Case | None,
            await self.session.scalar(
                select(Case)
                .where(
                    Case.organization_id == organization_id,
                    Case.id == case_id,
                    Case.archived_at.is_(None),
                )
                .with_for_update()
            ),
        )

    async def _risk_for_approval(
        self, organization_id: UUID, approval: Approval
    ) -> RiskAssessment | None:
        if approval.risk_assessment_id is None:
            return None
        return cast(
            RiskAssessment | None,
            await self.session.scalar(
                select(RiskAssessment).where(
                    RiskAssessment.id == approval.risk_assessment_id,
                    RiskAssessment.organization_id == organization_id,
                    RiskAssessment.case_id == approval.case_id,
                )
            ),
        )

    def _ensure_approval_viewer(self, principal: Principal) -> None:
        ensure_roles(principal, RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER)

    def _authorize_decision(
        self, principal: Principal, approval: Approval, case: Case, risk: RiskAssessment
    ) -> None:
        authorize_approval(
            principal,
            ApprovalAuthorizationInput(
                organization_id=approval.organization_id,
                submitted_by_user_id=case.submitted_by_user_id,
                risk_level=risk.risk_level,
                requires_approval=risk.requires_approval,
            ),
        )

    async def _is_active_approval_reviewer(self, organization_id: UUID, user_id: UUID) -> bool:
        user = cast(
            User | None,
            await self.session.scalar(
                select(User).where(
                    User.organization_id == organization_id,
                    User.id == user_id,
                    User.is_active.is_(True),
                )
            ),
        )
        if user is None:
            return False
        roles = tuple(
            (
                await self.session.scalars(
                    select(Role.name)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(
                        UserRole.organization_id == organization_id,
                        UserRole.user_id == user_id,
                    )
                )
            ).all()
        )
        return not _APPROVAL_ROLE_NAMES.isdisjoint(roles)


def _case_status_for_decision(decision: ReviewerDecision) -> str:
    return {
        ReviewerDecision.APPROVE: "approved",
        ReviewerDecision.EDIT_AND_APPROVE: "approved",
        ReviewerDecision.REJECT: "rejected",
        ReviewerDecision.REQUEST_MORE_EVIDENCE: "needs_more_evidence",
    }[decision]


def _lifecycle_for_decision(decision: ReviewerDecision) -> ApprovalLifecycle:
    return {
        ReviewerDecision.APPROVE: ApprovalLifecycle.APPROVED,
        ReviewerDecision.EDIT_AND_APPROVE: ApprovalLifecycle.APPROVED,
        ReviewerDecision.REJECT: ApprovalLifecycle.REJECTED,
        ReviewerDecision.REQUEST_MORE_EVIDENCE: ApprovalLifecycle.NEEDS_MORE_EVIDENCE,
    }[decision]
