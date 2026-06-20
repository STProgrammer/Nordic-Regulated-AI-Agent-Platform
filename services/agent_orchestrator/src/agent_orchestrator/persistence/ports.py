"""Ports implemented by the API data layer, never by graph code."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from agent_orchestrator.types import ModelUsage, RuntimeStatus, WorkflowContext


class WorkflowPersistence(Protocol):
    """Durable run/node lifecycle and model-usage operations, scoped by context."""

    async def claim_run(self, context: WorkflowContext) -> bool: ...

    async def start_node(
        self,
        context: WorkflowContext,
        *,
        node_name: str,
        input_summary: dict[str, object],
        retry_count: int,
    ) -> UUID: ...

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
    ) -> None: ...

    async def complete_run(
        self,
        context: WorkflowContext,
        *,
        status: RuntimeStatus,
        state_snapshot: dict[str, object],
        duration_ms: int,
    ) -> None: ...

    async def fail_run(
        self,
        context: WorkflowContext,
        *,
        state_snapshot: dict[str, object],
        duration_ms: int,
        error_code: str,
    ) -> None: ...

    async def record_model_usage(self, context: WorkflowContext, usage: ModelUsage) -> None: ...
