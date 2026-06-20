"""Immutable public value objects shared by all graph implementations."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuntimeStatus(StrEnum):
    """Closed durable statuses shared by workflow runs and the runtime."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowContext(BaseModel):
    """Trusted identifiers and graph identity; never caller-selectable at runtime."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_run_id: UUID
    organization_id: UUID
    case_id: UUID
    initiated_by_user_id: UUID
    workflow_name: Annotated[str, Field(min_length=1, max_length=100)]
    workflow_version: Annotated[str, Field(min_length=1, max_length=100)]


class RetryPolicy(BaseModel):
    """Finite retry policy where the count excludes the initial node attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    maximum_retries: Annotated[int, Field(ge=0, le=5)] = 1
    retryable_codes: frozenset[str] = frozenset({"provider_unavailable", "transient_failure"})


class NodeTiming(BaseModel):
    """Safe monotonic timing metadata persisted after a node finishes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    duration_ms: Annotated[int, Field(ge=0)]
    retry_count: Annotated[int, Field(ge=0)]


class TerminalOutcome(BaseModel):
    """The only terminal result the generic runtime exposes to its caller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal[RuntimeStatus.COMPLETED, RuntimeStatus.FAILED]
    error_code: str | None = None


class ModelUsage(BaseModel):
    """Provider accounting metadata that contains no request or response content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Annotated[str, Field(min_length=1, max_length=100)]
    model_name: Annotated[str, Field(min_length=1, max_length=255)]
    operation: Annotated[str, Field(min_length=1, max_length=100)]
    latency_ms: Annotated[int, Field(ge=0)]
    token_input: Annotated[int | None, Field(default=None, ge=0)] = None
    token_output: Annotated[int | None, Field(default=None, ge=0)] = None
    success: bool
    error_code: str | None = None
