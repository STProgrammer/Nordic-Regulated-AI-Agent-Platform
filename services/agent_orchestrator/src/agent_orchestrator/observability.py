"""Dependency-light telemetry port for graph and model-provider code."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from typing import Literal, Protocol


class AgentTelemetry(Protocol):
    """Safe subset of process telemetry available to agent orchestration."""

    def span(
        self, name: str, attributes: Mapping[str, str | int | float] | None = None
    ) -> AbstractContextManager[None]: ...

    def workflow_run(self, *, workflow_name: str, outcome: str) -> None: ...

    def workflow_node(
        self, *, workflow_name: str, node_name: str, outcome: str, duration_ms: int
    ) -> None: ...

    def model(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        outcome: Literal["success", "failure"],
        latency_ms: int | None,
        token_input: int | None = None,
        token_output: int | None = None,
    ) -> None: ...


class _NoopAgentTelemetry:
    def span(
        self, name: str, attributes: Mapping[str, str | int | float] | None = None
    ) -> AbstractContextManager[None]:
        del name, attributes
        return nullcontext()

    def workflow_run(self, *, workflow_name: str, outcome: str) -> None:
        del workflow_name, outcome

    def workflow_node(
        self, *, workflow_name: str, node_name: str, outcome: str, duration_ms: int
    ) -> None:
        del workflow_name, node_name, outcome, duration_ms

    def model(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        outcome: Literal["success", "failure"],
        latency_ms: int | None,
        token_input: int | None = None,
        token_output: int | None = None,
    ) -> None:
        del provider, model, operation, outcome, latency_ms, token_input, token_output


_telemetry: AgentTelemetry = _NoopAgentTelemetry()


def configure_agent_telemetry(telemetry: AgentTelemetry) -> None:
    """Install the process-owned adapter without importing application code here."""

    global _telemetry
    _telemetry = telemetry


def get_agent_telemetry() -> AgentTelemetry:
    """Return a no-op adapter until the worker bootstrap supplies one."""

    return _telemetry


def reset_agent_telemetry() -> None:
    """Restore no-op behavior for isolated unit tests."""

    global _telemetry
    _telemetry = _NoopAgentTelemetry()
