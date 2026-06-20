"""The deliberately small shared state envelope for case-owned graphs."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from agent_orchestrator.types import RuntimeStatus, WorkflowContext


class CaseWorkflowState(BaseModel):
    """Base state that excludes case text, prompts, model bodies, and credentials."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    context: WorkflowContext
    state_schema_version: Annotated[str, Field(min_length=1, max_length=32)] = "v1"
    status: RuntimeStatus = RuntimeStatus.QUEUED
    target_language: str | None = None
    approval_required: bool = False
    reason_codes: tuple[str, ...] = ()
