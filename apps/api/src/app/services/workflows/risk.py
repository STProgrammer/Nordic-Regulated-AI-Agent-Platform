"""Closed deterministic Risk and Compliance workflow service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.graphs.risk_types import (
    FinalRiskLevel,
    RiskAssessmentResult,
    RiskReason,
    RiskSafeNextState,
    RiskSignals,
    RiskWorkflowState,
)
from agent_orchestrator.types import WorkflowContext
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.workflow import AgentMessage, RetrievedSource, RiskAssessment, WorkflowRun
from app.db.repositories.case import CaseRepository
from app.services.audit.service import AuditEventCreate, AuditService
from app.services.auth.policy import CaseAction, authorize_case_action
from app.services.auth.principal import Principal
from app.services.errors import ConflictError, NotFoundError, WorkflowUnavailableError
from app.services.workflows.dispatch import WorkflowTaskDispatcher
from app.services.workflows.service import WorkflowRunCreate, WorkflowRunService

RISK_WORKFLOW_NAME = "risk_compliance"
RISK_WORKFLOW_VERSION = "phase21-v1"
_DRAFTING_WORKFLOW_NAME = "drafting"
_EVIDENCE_WORKFLOW_NAME = "evidence"
_INTAKE_WORKFLOW_NAME = "intake"
_EXTRACTION_WORKFLOW_NAME = "extraction"
_SENSITIVE_DOMAINS = frozenset({"banking_compliance", "public_sector"})
_HIGH_IMPACT_DOMAINS = frozenset({"banking_compliance", "energy_operations"})
_HIGH_IMPACT_CASE_TYPES = frozenset({"compliance_review", "operational_incident"})
_KNOWN_DOMAINS = frozenset(
    {"public_sector", "banking_compliance", "energy_operations", "internal_policy"}
)
_KNOWN_CASE_TYPES = frozenset(
    {
        "case_support",
        "compliance_review",
        "operational_incident",
        "policy_question",
        "document_intelligence",
        "unknown",
    }
)


@dataclass(frozen=True)
class RiskPrerequisites:
    """Only safe worker-loaded policy signals; raw draft and source text never escape."""

    signals: RiskSignals


@dataclass(frozen=True)
class RiskAssessmentRecord:
    """Read-only safe assessment presentation returned by the dedicated route."""

    workflow_run_id: UUID
    result: RiskAssessmentResult


class RiskWorkflowService:
    """Own risk-run start and latest-assessment reads; execution remains worker-only."""

    def __init__(
        self, session: AsyncSession, *, dispatcher: WorkflowTaskDispatcher | None = None
    ) -> None:
        self.session = session
        self._workflows = WorkflowRunService(session)
        self._cases = CaseRepository(session)
        self._audit = AuditService(session)
        self._dispatcher = dispatcher

    async def start(self, principal: Principal, case_id: UUID) -> WorkflowRun:
        """Queue one risk assessment only after server-owned prerequisite revalidation."""

        authorize_case_action(principal, CaseAction.EDIT)
        case = await self._cases.get(principal.organization_id, case_id)
        if case is None or case.status == "archived":
            raise NotFoundError("Case")
        if await self._active_run(principal.organization_id, case.id) is not None:
            raise ConflictError("Risk and Compliance workflow")
        if await load_risk_prerequisites(self.session, principal.organization_id, case.id) is None:
            return await self._record_needs_more_evidence(principal, case.id)

        run = await self._workflows.create(
            WorkflowRunCreate(
                organization_id=principal.organization_id,
                case_id=case.id,
                started_by_user_id=principal.user_id,
                workflow_name=RISK_WORKFLOW_NAME,
                workflow_version=RISK_WORKFLOW_VERSION,
                status="queued",
                started_at=datetime.now(UTC),
                state_snapshot={
                    "workflow_name": RISK_WORKFLOW_NAME,
                    "workflow_version": RISK_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "queued",
                },
            )
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.risk_compliance_queued",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case.id,
                event_data={"workflow": RISK_WORKFLOW_NAME, "status": "queued"},
            )
        )
        await self.session.commit()
        if self._dispatcher is not None:
            try:
                self._dispatcher.dispatch_risk_compliance(run.id)
            except Exception as error:
                await self._mark_dispatch_failed(run, principal)
                raise WorkflowUnavailableError() from error
        return run

    async def get_latest_assessment(
        self, principal: Principal, case_id: UUID
    ) -> RiskAssessmentRecord:
        """Return the latest completed safe assessment for a readable current-tenant case."""

        authorize_case_action(principal, CaseAction.READ)
        if await self._cases.get(principal.organization_id, case_id) is None:
            raise NotFoundError("Case")
        assessment = cast(
            RiskAssessment | None,
            await self.session.scalar(
                select(RiskAssessment)
                .join(
                    WorkflowRun,
                    (WorkflowRun.id == RiskAssessment.workflow_run_id)
                    & (WorkflowRun.organization_id == RiskAssessment.organization_id),
                )
                .where(
                    RiskAssessment.organization_id == principal.organization_id,
                    RiskAssessment.case_id == case_id,
                    WorkflowRun.workflow_name == RISK_WORKFLOW_NAME,
                    WorkflowRun.status == "completed",
                )
                .order_by(desc(RiskAssessment.inserted_at), desc(RiskAssessment.id))
            ),
        )
        if assessment is None:
            raise NotFoundError("Risk assessment")
        codes = assessment.risk_reasons.get("codes")
        next_state = assessment.risk_reasons.get("safe_next_state")
        if (
            not isinstance(codes, list)
            or not isinstance(next_state, str)
            or not all(isinstance(code, str) for code in codes)
        ):
            raise NotFoundError("Risk assessment")
        try:
            result = RiskAssessmentResult(
                risk_level=FinalRiskLevel(assessment.risk_level),
                risk_reasons=tuple(RiskReason(code) for code in codes),
                requires_approval=assessment.requires_approval,
                safe_next_state=RiskSafeNextState(next_state),
            )
        except ValueError as error:
            raise NotFoundError("Risk assessment") from error
        return RiskAssessmentRecord(workflow_run_id=assessment.workflow_run_id, result=result)

    async def _active_run(self, organization_id: UUID, case_id: UUID) -> WorkflowRun | None:
        return cast(
            WorkflowRun | None,
            await self.session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == RISK_WORKFLOW_NAME,
                    WorkflowRun.status.in_(("queued", "running")),
                )
                .order_by(desc(WorkflowRun.started_at), desc(WorkflowRun.id))
            ),
        )

    async def _record_needs_more_evidence(self, principal: Principal, case_id: UUID) -> WorkflowRun:
        run = await self._workflows.create(
            WorkflowRunCreate(
                organization_id=principal.organization_id,
                case_id=case_id,
                started_by_user_id=principal.user_id,
                workflow_name=RISK_WORKFLOW_NAME,
                workflow_version=RISK_WORKFLOW_VERSION,
                status="needs_more_evidence",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                duration_ms=0,
                state_snapshot={
                    "workflow_name": RISK_WORKFLOW_NAME,
                    "workflow_version": RISK_WORKFLOW_VERSION,
                    "state_schema_version": "v1",
                    "status": "needs_more_evidence",
                },
            )
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.risk_compliance_needs_more_evidence",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=case_id,
                event_data={"workflow": RISK_WORKFLOW_NAME, "status": "needs_more_evidence"},
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
            "workflow_name": RISK_WORKFLOW_NAME,
            "workflow_version": RISK_WORKFLOW_VERSION,
            "state_schema_version": "v1",
            "status": "failed",
        }
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="workflow.risk_compliance_failed",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data={
                    "workflow": RISK_WORKFLOW_NAME,
                    "status": "failed",
                    "reason_code": "dispatch_unavailable",
                },
            )
        )
        await self.session.commit()


async def load_risk_prerequisites(
    session: AsyncSession, organization_id: UUID, case_id: UUID
) -> RiskPrerequisites | None:
    """Revalidate a protected Draft, current eligible Evidence, and trusted Intake signals.

    The queries intentionally load no case description, draft content, source excerpts,
    prompt, provider, or extracted-field values.  They return only bounded policy facts.
    """

    case = await CaseRepository(session).get(organization_id, case_id)
    if case is None or case.status == "archived":
        return None
    draft_run = await _latest_completed_run(
        session, organization_id, case_id, _DRAFTING_WORKFLOW_NAME
    )
    evidence_run = await _latest_completed_run(
        session, organization_id, case_id, _EVIDENCE_WORKFLOW_NAME
    )
    intake_run = await _latest_completed_run(
        session, organization_id, case_id, _INTAKE_WORKFLOW_NAME
    )
    if draft_run is None or evidence_run is None or intake_run is None:
        return None
    if draft_run.state_snapshot.get("draft_available") is not True:
        return None
    if (
        evidence_run.state_snapshot.get("evidence_outcome") != "completed"
        or evidence_run.state_snapshot.get("evidence_sufficient") is not True
        or evidence_run.state_snapshot.get("contradiction_detected") is not False
    ):
        return None
    draft_metadata = await session.scalar(
        select(AgentMessage.structured_output).where(
            AgentMessage.organization_id == organization_id,
            AgentMessage.case_id == case_id,
            AgentMessage.workflow_run_id == draft_run.id,
            AgentMessage.message_type == "draft",
            AgentMessage.role == "assistant",
        )
    )
    draft_labels = _draft_citation_labels(draft_metadata)
    evidence_labels = _citation_labels(evidence_run.state_snapshot.get("citation_labels"))
    if not draft_labels or not evidence_labels:
        return None
    draft_source_labels = await _current_approved_source_labels(
        session, organization_id, case_id, draft_run.id
    )
    if not set(draft_labels).issubset(draft_source_labels):
        return None
    if (
        await _current_approved_source_labels(session, organization_id, case_id, evidence_run.id)
        != evidence_labels
    ):
        return None

    intake = intake_run.state_snapshot
    pii_detected = _bool(intake, "pii_detected")
    prompt_injection_detected = _bool(intake, "prompt_injection_detected")
    intake_low_confidence = _bool(intake, "low_confidence")
    recommended_domain = intake.get("recommended_domain")
    classification_case_type = intake.get("classification_case_type")
    if (
        pii_detected is None
        or prompt_injection_detected is None
        or intake_low_confidence is None
        or not isinstance(recommended_domain, str)
        or not isinstance(classification_case_type, str)
    ):
        return None

    extraction_low_confidence, extraction_policy_conflict = await _extraction_signals(
        session, organization_id, case_id
    )
    domain_known = case.domain in _KNOWN_DOMAINS and recommended_domain in _KNOWN_DOMAINS
    type_known = classification_case_type in _KNOWN_CASE_TYPES
    policy_conflict = (
        extraction_policy_conflict
        or not domain_known
        or not type_known
        or recommended_domain != case.domain
    )
    high_impact_action = (
        case.domain in _HIGH_IMPACT_DOMAINS and classification_case_type in _HIGH_IMPACT_CASE_TYPES
    )
    return RiskPrerequisites(
        signals=RiskSignals(
            pii_detected=pii_detected,
            sensitive_domain=case.domain in _SENSITIVE_DOMAINS,
            low_confidence=intake_low_confidence or extraction_low_confidence,
            high_impact_action=high_impact_action,
            policy_conflict=policy_conflict,
            prompt_injection_detected=prompt_injection_detected,
        )
    )


async def persist_risk_assessment(
    session: AsyncSession,
    context: WorkflowContext,
    state: RiskWorkflowState,
    result: RiskAssessmentResult,
) -> None:
    """Atomically persist one safe assessment and the Case risk projection."""

    prerequisites = await load_risk_prerequisites(session, context.organization_id, context.case_id)
    if prerequisites is None or prerequisites.signals != _signals_from_state(state):
        raise ControlledWorkflowError("risk_prerequisite_changed")
    if result.risk_level is not state.final_risk_level:
        raise ControlledWorkflowError("invalid_risk_policy_state")

    cases = CaseRepository(session)
    async with session.begin_nested():
        case = await cases.get(context.organization_id, context.case_id)
        if case is None or case.status == "archived":
            raise ControlledWorkflowError("case_not_available")
        existing = cast(
            RiskAssessment | None,
            await session.scalar(
                select(RiskAssessment)
                .where(
                    RiskAssessment.organization_id == context.organization_id,
                    RiskAssessment.workflow_run_id == context.workflow_run_id,
                )
                .with_for_update()
            ),
        )
        if existing is None:
            assessment = RiskAssessment(
                organization_id=context.organization_id,
                case_id=context.case_id,
                workflow_run_id=context.workflow_run_id,
                risk_level=result.risk_level.value,
                risk_reasons={
                    "schema_version": "v1",
                    "codes": [reason.value for reason in result.risk_reasons],
                    "safe_next_state": result.safe_next_state.value,
                },
                pii_detected=state.pii_detected,
                prompt_injection_detected=state.prompt_injection_detected,
                weak_evidence=state.weak_evidence,
                high_impact_action=state.high_impact_action,
                requires_approval=result.requires_approval,
            )
            session.add(assessment)
        case.risk_level = result.risk_level.value
        await session.flush()


async def _latest_completed_run(
    session: AsyncSession, organization_id: UUID, case_id: UUID, workflow_name: str
) -> WorkflowRun | None:
    return cast(
        WorkflowRun | None,
        await session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.case_id == case_id,
                WorkflowRun.workflow_name == workflow_name,
                WorkflowRun.status == "completed",
            )
            .order_by(desc(WorkflowRun.finished_at), desc(WorkflowRun.id))
        ),
    )


async def _current_approved_source_labels(
    session: AsyncSession, organization_id: UUID, case_id: UUID, workflow_run_id: UUID
) -> tuple[str, ...]:
    labels = tuple(
        (
            await session.scalars(
                select(RetrievedSource.citation_label)
                .join(
                    Document,
                    (Document.id == RetrievedSource.document_id)
                    & (Document.organization_id == RetrievedSource.organization_id),
                )
                .where(
                    RetrievedSource.organization_id == organization_id,
                    RetrievedSource.case_id == case_id,
                    RetrievedSource.workflow_run_id == workflow_run_id,
                    Document.archived_at.is_(None),
                    Document.source_status == "approved",
                )
                .order_by(RetrievedSource.rank.asc(), RetrievedSource.id.asc())
            )
        ).all()
    )
    if (
        not labels
        or len(set(labels)) != len(labels)
        or not all(isinstance(label, str) for label in labels)
    ):
        return ()
    return labels


async def _extraction_signals(
    session: AsyncSession, organization_id: UUID, case_id: UUID
) -> tuple[bool, bool]:
    run = await _latest_completed_run(session, organization_id, case_id, _EXTRACTION_WORKFLOW_NAME)
    if run is None:
        return False, False
    count = run.state_snapshot.get("low_confidence_field_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        return False, True
    return count > 0, False


def _bool(snapshot: dict[str, object], key: str) -> bool | None:
    value = snapshot.get(key)
    return value if isinstance(value, bool) else None


def _citation_labels(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        return ()
    labels = tuple(value)
    if len(set(labels)) != len(labels) or not all(
        isinstance(label, str) and len(label) <= 16 for label in labels
    ):
        return ()
    return cast(tuple[str, ...], labels)


def _draft_citation_labels(metadata: object) -> tuple[str, ...]:
    """Read only the copied closed labels, never the protected original draft text."""

    return _citation_labels(metadata.get("citation_labels") if isinstance(metadata, dict) else None)


def _signals_from_state(state: RiskWorkflowState) -> RiskSignals:
    return RiskSignals(
        pii_detected=state.pii_detected,
        sensitive_domain=state.sensitive_domain,
        weak_evidence=state.weak_evidence,
        contradictory_evidence=state.contradictory_evidence,
        missing_required_source=state.missing_required_source,
        low_confidence=state.low_confidence,
        high_impact_action=state.high_impact_action,
        policy_conflict=state.policy_conflict,
        prompt_injection_detected=state.prompt_injection_detected,
    )
