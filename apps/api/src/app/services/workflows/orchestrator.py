"""API-side adapters for agent ports and Intake-specific durable policy."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from agent_orchestrator.graphs.intake_types import IntakeWorkflowState
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.prompts.base import EffectivePrompt, PromptLoader
from agent_orchestrator.types import ModelUsage, RuntimeStatus, WorkflowContext
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.prompt import ModelUsageRecord, PromptVersion
from app.db.repositories.case import CaseRepository, CaseUpdateValues
from app.services.audit.service import AuditEventCreate, AuditService, JSONValue
from app.services.common.persistence import stage_write
from app.services.workflows.service import (
    WorkflowNodeFinish,
    WorkflowNodeStart,
    WorkflowRunFinalize,
    WorkflowRunService,
    WorkflowToolCallCreate,
)


class SqlAlchemyPromptLoader(PromptLoader):
    """Resolve an organization override before a global active prompt deterministically."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_active(self, organization_id: UUID, prompt_name: str) -> EffectivePrompt:
        organization_prompt = await self._session.scalar(
            select(PromptVersion)
            .where(
                PromptVersion.organization_id == organization_id,
                PromptVersion.name == prompt_name,
                PromptVersion.is_active.is_(True),
            )
            .order_by(desc(PromptVersion.updated_at), desc(PromptVersion.id))
        )
        prompt = organization_prompt
        if prompt is None:
            prompt = await self._session.scalar(
                select(PromptVersion)
                .where(
                    PromptVersion.organization_id.is_(None),
                    PromptVersion.name == prompt_name,
                    PromptVersion.is_active.is_(True),
                )
                .order_by(desc(PromptVersion.updated_at), desc(PromptVersion.id))
            )
        if prompt is None:
            from agent_orchestrator.errors import PromptNotConfiguredError

            raise PromptNotConfiguredError()
        return EffectivePrompt(
            prompt_id=prompt.id,
            name=prompt.name,
            version=prompt.version,
            organization_id=prompt.organization_id,
            content=prompt.content,
        )


class SqlAlchemyWorkflowPersistence(WorkflowPersistence):
    """Adapt typed graph lifecycle events to tenant-safe SQLAlchemy services."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._workflows = WorkflowRunService(session)
        self._audit = AuditService(session)

    async def claim_run(self, context: WorkflowContext) -> bool:
        run = await self._workflows.claim_queued(context.organization_id, context.workflow_run_id)
        if (
            run is None
            or run.case_id != context.case_id
            or run.started_by_user_id != context.initiated_by_user_id
            or run.workflow_name != context.workflow_name
            or run.workflow_version != context.workflow_version
        ):
            return False
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=context.organization_id,
                actor_user_id=context.initiated_by_user_id,
                event_type=f"workflow.{context.workflow_name}_started",
                resource_type="workflow_run",
                resource_id=context.workflow_run_id,
                case_id=context.case_id,
                event_data={"workflow": context.workflow_name, "status": "running"},
            )
        )
        return True

    async def claim_paused_run(self, context: WorkflowContext) -> bool:
        """Resume a claimed review interruption without permitting generic resume routes."""

        run = await self._workflows.claim_waiting_for_human_review(
            context.organization_id, context.workflow_run_id
        )
        return not (
            run is None
            or run.case_id != context.case_id
            or run.started_by_user_id != context.initiated_by_user_id
            or run.workflow_name != context.workflow_name
            or run.workflow_version != context.workflow_version
        )

    async def start_node(
        self,
        context: WorkflowContext,
        *,
        node_name: str,
        input_summary: dict[str, object],
        retry_count: int,
    ) -> UUID:
        node = await self._workflows.start_node(
            WorkflowNodeStart(
                organization_id=context.organization_id,
                workflow_run_id=context.workflow_run_id,
                node_name=node_name,
                started_at=datetime.now(UTC),
                input_summary=input_summary,
                retry_count=retry_count,
            )
        )
        return node.id

    async def finish_node(
        self,
        context: WorkflowContext,
        *,
        node_run_id: UUID,
        status: RuntimeStatus,
        output_summary: dict[str, object],
        duration_ms: int,
        retry_count: int,
        error_code: str | None = None,
    ) -> None:
        await self._workflows.finish_node(
            WorkflowNodeFinish(
                organization_id=context.organization_id,
                workflow_run_id=context.workflow_run_id,
                node_run_id=node_run_id,
                status=status.value,
                finished_at=datetime.now(UTC),
                duration_ms=duration_ms,
                output_summary=output_summary,
                retry_count=retry_count,
                error_summary=error_code,
            )
        )

    async def complete_run(
        self,
        context: WorkflowContext,
        *,
        status: RuntimeStatus,
        state_snapshot: dict[str, object],
        duration_ms: int,
    ) -> None:
        completed = await self._workflows.finalize(
            WorkflowRunFinalize(
                organization_id=context.organization_id,
                workflow_run_id=context.workflow_run_id,
                status=status.value,
                finished_at=datetime.now(UTC),
                duration_ms=duration_ms,
                state_snapshot=state_snapshot,
            )
        )
        if completed is None:
            return
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=context.organization_id,
                actor_user_id=context.initiated_by_user_id,
                event_type=(
                    f"workflow.{context.workflow_name}_needs_more_evidence"
                    if status is RuntimeStatus.NEEDS_MORE_EVIDENCE
                    else f"workflow.{context.workflow_name}_completed"
                ),
                resource_type="workflow_run",
                resource_id=context.workflow_run_id,
                case_id=context.case_id,
                event_data=_audit_workflow_data(state_snapshot, status=status.value),
            )
        )

    async def pause_run(
        self,
        context: WorkflowContext,
        *,
        state_snapshot: dict[str, object],
        duration_ms: int,
    ) -> None:
        paused = await self._workflows.pause(
            WorkflowRunFinalize(
                organization_id=context.organization_id,
                workflow_run_id=context.workflow_run_id,
                status=RuntimeStatus.WAITING_FOR_HUMAN_REVIEW.value,
                finished_at=datetime.now(UTC),
                duration_ms=duration_ms,
                state_snapshot=state_snapshot,
            )
        )
        if paused is None:
            return
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=context.organization_id,
                actor_user_id=context.initiated_by_user_id,
                event_type=f"workflow.{context.workflow_name}_interrupted",
                resource_type="workflow_run",
                resource_id=context.workflow_run_id,
                case_id=context.case_id,
                event_data=_audit_workflow_data(
                    state_snapshot, status=RuntimeStatus.WAITING_FOR_HUMAN_REVIEW.value
                ),
            )
        )

    async def fail_run(
        self,
        context: WorkflowContext,
        *,
        state_snapshot: dict[str, object],
        duration_ms: int,
        error_code: str,
    ) -> None:
        failed = await self._workflows.finalize(
            WorkflowRunFinalize(
                organization_id=context.organization_id,
                workflow_run_id=context.workflow_run_id,
                status=RuntimeStatus.FAILED.value,
                finished_at=datetime.now(UTC),
                duration_ms=duration_ms,
                state_snapshot=state_snapshot,
                error_summary=error_code,
            )
        )
        if failed is None:
            return
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=context.organization_id,
                actor_user_id=context.initiated_by_user_id,
                event_type=f"workflow.{context.workflow_name}_failed",
                resource_type="workflow_run",
                resource_id=context.workflow_run_id,
                case_id=context.case_id,
                event_data={
                    "workflow": context.workflow_name,
                    "status": "failed",
                    "reason_code": error_code,
                },
            )
        )

    async def record_model_usage(self, context: WorkflowContext, usage: ModelUsage) -> None:
        # Fixture plumbing validates the same schema but is not an external model attempt.
        if usage.provider == "deterministic":
            return
        record = ModelUsageRecord(
            organization_id=context.organization_id,
            case_id=context.case_id,
            workflow_run_id=context.workflow_run_id,
            provider=usage.provider,
            model_name=usage.model_name,
            operation=usage.operation,
            token_input=usage.token_input,
            token_output=usage.token_output,
            cost_estimate=None,
            latency_ms=usage.latency_ms,
            success=usage.success,
            error_summary=usage.error_code,
        )
        await stage_write(
            self._session,
            lambda: self._add_model_usage(record),
            resource="Model usage record",
        )

    async def record_tool_call(
        self,
        context: WorkflowContext,
        *,
        node_run_id: UUID | None,
        tool_name: str,
        status: str,
        started_at: datetime,
        finished_at: datetime,
        duration_ms: int,
        retry_count: int,
        input_summary: dict[str, object],
        output_summary: dict[str, object],
        error_code: str | None = None,
    ) -> None:
        """Persist a ToolRegistry event without accepting tool payloads or result bodies."""

        await self._workflows.record_tool_call(
            WorkflowToolCallCreate(
                organization_id=context.organization_id,
                workflow_run_id=context.workflow_run_id,
                workflow_node_run_id=node_run_id,
                tool_name=tool_name,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                retry_count=retry_count,
                input_summary=input_summary,
                output_summary=output_summary,
                error_summary=error_code,
            )
        )

    async def _add_model_usage(self, record: ModelUsageRecord) -> ModelUsageRecord:
        self._session.add(record)
        return record


async def persist_intake_case_result(
    session: AsyncSession, context: WorkflowContext, state: IntakeWorkflowState
) -> None:
    """Update only high-confidence engine-owned Case fields, never lifecycle status."""

    if state.low_confidence:
        return
    cases = CaseRepository(session)
    case = await cases.get(context.organization_id, context.case_id)
    if case is None:
        from agent_orchestrator.errors import ControlledWorkflowError

        raise ControlledWorkflowError("case_not_available")
    domain = state.recommended_domain
    if domain is None:
        from agent_orchestrator.errors import ControlledWorkflowError

        raise ControlledWorkflowError("invalid_classification")
    await stage_write(
        session,
        lambda: cases.update(
            case,
            CaseUpdateValues(
                case_type=state.classification_case_type.value,
                domain=domain.value,
                risk_level=state.preliminary_risk_level.value,
            ),
        ),
        resource="Case",
    )


def _audit_workflow_data(snapshot: dict[str, object], *, status: str) -> dict[str, JSONValue]:
    """Select only audit-safe closed labels, counts, and booleans from a safe snapshot."""

    allowed = {
        "workflow_name",
        "status",
        "low_confidence",
        "pii_detected",
        "prompt_injection_detected",
        "classification_case_type",
        "recommended_domain",
        "preliminary_risk_level",
        "approval_required",
        "suggested_workflow",
        "evidence_outcome",
        "evidence_sufficient",
        "contradiction_detected",
        "evidence_source_count",
        "vector_candidate_count",
        "keyword_candidate_count",
        "merged_candidate_count",
        "reranked_source_count",
        "permitted_source_count",
        "approved_source_count",
        "reason_codes",
        "final_risk_level",
        "safe_next_state",
        "sensitive_domain",
        "weak_evidence",
        "missing_required_source",
        "high_impact_action",
        "policy_conflict",
    }
    data = cast(
        dict[str, JSONValue], {key: value for key, value in snapshot.items() if key in allowed}
    )
    data["status"] = status
    return data
