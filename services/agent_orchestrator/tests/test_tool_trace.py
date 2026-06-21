"""Metadata-only trace coverage for startup-registered workflow tools."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.tools.registry import RegisteredTool, ToolRegistry
from agent_orchestrator.types import WorkflowContext
from pydantic import BaseModel, ConfigDict

_SENTINEL = "phase23-raw-payload-must-never-persist"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization: str
    value: str


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class Recorder:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

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
        self.events.append(
            {
                "context": context,
                "node_run_id": node_run_id,
                "tool_name": tool_name,
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "retry_count": retry_count,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "error_code": error_code,
            }
        )


def _context() -> WorkflowContext:
    return WorkflowContext(
        workflow_run_id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        initiated_by_user_id=uuid4(),
        workflow_name="synthetic",
        workflow_version="v1",
    )


def _registry(recorder: Recorder) -> ToolRegistry:
    async def handler(value: BaseModel) -> BaseModel:
        parsed = Input.model_validate(value)
        return Output(value=f"result:{parsed.value}")

    registry = ToolRegistry(recorder=recorder)
    registry.register(
        RegisteredTool(
            name="synthetic_tool",
            description="Test-only metadata trace capability.",
            input_model=Input,
            output_model=Output,
            handler=handler,
            allowed_graphs=frozenset({"synthetic"}),
        )
    )
    return registry


def test_registered_tool_records_only_shape_and_controlled_success_metadata() -> None:
    async def run() -> Recorder:
        recorder = Recorder()
        result, duration = await _registry(recorder).invoke(
            "synthetic",
            "synthetic_tool",
            {"authorization": _SENTINEL, "value": _SENTINEL},
            context=_context(),
            node_run_id=uuid4(),
        )
        assert isinstance(result, Output)
        assert result.value.endswith(_SENTINEL)
        assert duration >= 0
        return recorder

    recorder = asyncio.run(run())
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert event["status"] == "succeeded"
    assert event["error_code"] is None
    assert event["input_summary"] == {"field_names": ["authorization", "value"]}
    assert event["output_summary"] == {"field_names": ["value"]}
    assert _SENTINEL not in repr(event)


def test_invalid_registered_tool_input_records_a_controlled_rejection_without_payload() -> None:
    async def run() -> Recorder:
        recorder = Recorder()
        with pytest.raises(ControlledWorkflowError, match="tool_validation_failed"):
            await _registry(recorder).invoke(
                "synthetic",
                "synthetic_tool",
                {"authorization": _SENTINEL},
                context=_context(),
            )
        return recorder

    recorder = asyncio.run(run())
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert event["status"] == "rejected"
    assert event["error_code"] == "tool_validation_failed"
    assert _SENTINEL not in repr(event)
