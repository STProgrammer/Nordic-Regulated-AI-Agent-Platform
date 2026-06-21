"""Deterministic graph/model telemetry coverage without an API dependency."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

from agent_orchestrator.graphs.runtime import GraphNode, GraphRuntime
from agent_orchestrator.model_providers.base import StructuredModelRequest
from agent_orchestrator.model_providers.deterministic import DeterministicModelProvider
from agent_orchestrator.observability import configure_agent_telemetry, reset_agent_telemetry
from agent_orchestrator.prompts.base import EffectivePrompt
from agent_orchestrator.types import RetryPolicy, RuntimeStatus, WorkflowContext
from pydantic import BaseModel


class _State(BaseModel):
    count: int = 0


class _Persistence:
    async def claim_run(self, _context: WorkflowContext) -> bool:
        return True

    async def claim_paused_run(self, _context: WorkflowContext) -> bool:
        return True

    async def start_node(self, _context: WorkflowContext, **_kwargs: object) -> UUID:
        return uuid4()

    async def finish_node(self, _context: WorkflowContext, **_kwargs: object) -> None:
        return None

    async def complete_run(self, _context: WorkflowContext, **_kwargs: object) -> None:
        return None

    async def pause_run(self, _context: WorkflowContext, **_kwargs: object) -> None:
        return None

    async def fail_run(self, _context: WorkflowContext, **_kwargs: object) -> None:
        return None


class _Telemetry:
    def __init__(self) -> None:
        self.runs: list[tuple[str, str]] = []
        self.nodes: list[tuple[str, str, str]] = []
        self.models: list[tuple[str, str]] = []

    @contextmanager
    def span(self, _name: str, _attributes: object = None) -> Iterator[None]:
        yield

    def workflow_run(self, *, workflow_name: str, outcome: str) -> None:
        self.runs.append((workflow_name, outcome))

    def workflow_node(
        self, *, workflow_name: str, node_name: str, outcome: str, duration_ms: int
    ) -> None:
        del duration_ms
        self.nodes.append((workflow_name, node_name, outcome))

    def model(self, *, operation: str, outcome: str, **_kwargs: object) -> None:
        self.models.append((operation, outcome))


def _context() -> WorkflowContext:
    return WorkflowContext(
        workflow_run_id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        initiated_by_user_id=uuid4(),
        workflow_name="deterministic_test",
        workflow_version="v1",
    )


def test_graph_and_deterministic_model_emit_bounded_observations() -> None:
    async def increment(state: _State) -> dict[str, int]:
        return {"count": state.count + 1}

    telemetry = _Telemetry()
    configure_agent_telemetry(telemetry)
    try:
        graph = GraphRuntime[_State](
            state_model=_State,
            persistence=_Persistence(),  # type: ignore[arg-type]
            retry_policy=RetryPolicy(),
        )
        result = asyncio.run(graph.run(_context(), _State(), (GraphNode("increment", increment),)))
        provider = DeterministicModelProvider({"fixture": {"count": 3}})
        completion = asyncio.run(
            provider.complete(
                StructuredModelRequest(
                    operation="fixture",
                    prompt=EffectivePrompt(
                        prompt_id=uuid4(),
                        name="fixture",
                        version="v1",
                        organization_id=None,
                        content="server-owned",
                    ),
                    input_payload={},
                    output_model=_State,
                )
            )
        )
    finally:
        reset_agent_telemetry()

    assert result.outcome.status is RuntimeStatus.COMPLETED
    assert completion.output == {"count": 3}
    assert telemetry.runs == [("deterministic_test", "completed")]
    assert telemetry.nodes == [("deterministic_test", "increment", "completed")]
    assert telemetry.models == [("fixture", "success")]
