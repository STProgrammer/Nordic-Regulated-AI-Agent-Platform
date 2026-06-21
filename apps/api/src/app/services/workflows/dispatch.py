"""UUID-only dispatch boundary for the closed Intake graph task."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.core.observability import inject_trace_headers


class WorkflowTaskDispatcher(Protocol):
    """Submit a durable workflow-run identifier, never graph input or provider controls."""

    def dispatch_intake(self, workflow_run_id: UUID) -> None: ...

    def dispatch_evidence(self, workflow_run_id: UUID) -> None: ...

    def dispatch_extraction(self, workflow_run_id: UUID) -> None: ...
    def dispatch_drafting(self, workflow_run_id: UUID) -> None: ...

    def dispatch_risk_compliance(self, workflow_run_id: UUID) -> None: ...

    def dispatch_human_approval(self, workflow_run_id: UUID) -> None: ...


class CeleryWorkflowTaskDispatcher:
    """Production dispatcher for exactly one Phase-17 workflow task."""

    def dispatch_intake(self, workflow_run_id: UUID) -> None:
        from app.workers.tasks import run_intake_workflow_task

        run_intake_workflow_task.apply_async(
            args=[str(workflow_run_id)], headers=inject_trace_headers()
        )

    def dispatch_evidence(self, workflow_run_id: UUID) -> None:
        from app.workers.tasks import run_evidence_workflow_task

        run_evidence_workflow_task.apply_async(
            args=[str(workflow_run_id)], headers=inject_trace_headers()
        )

    def dispatch_extraction(self, workflow_run_id: UUID) -> None:
        from app.workers.tasks import run_extraction_workflow_task

        run_extraction_workflow_task.apply_async(
            args=[str(workflow_run_id)], headers=inject_trace_headers()
        )

    def dispatch_drafting(self, workflow_run_id: UUID) -> None:
        from app.workers.tasks import run_drafting_workflow_task

        run_drafting_workflow_task.apply_async(
            args=[str(workflow_run_id)], headers=inject_trace_headers()
        )

    def dispatch_risk_compliance(self, workflow_run_id: UUID) -> None:
        from app.workers.tasks import run_risk_compliance_workflow_task

        run_risk_compliance_workflow_task.apply_async(
            args=[str(workflow_run_id)], headers=inject_trace_headers()
        )

    def dispatch_human_approval(self, workflow_run_id: UUID) -> None:
        from app.workers.tasks import run_human_approval_workflow_task

        run_human_approval_workflow_task.apply_async(
            args=[str(workflow_run_id)], headers=inject_trace_headers()
        )
