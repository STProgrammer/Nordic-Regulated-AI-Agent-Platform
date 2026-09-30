"""Typed registry that prevents graph state from selecting arbitrary tools."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ValidationError

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.persistence.ports import ToolCallRecorder
from agent_orchestrator.types import WorkflowContext

ToolHandler = Callable[[BaseModel], Awaitable[BaseModel]]


@dataclass(frozen=True)
class RegisteredTool:
    """A startup-registered capability with declared input and output schemas."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler
    allowed_graphs: frozenset[str]


class ToolRegistry:
    """Allow only explicitly registered tools for the owning graph."""

    def __init__(self, *, recorder: ToolCallRecorder | None = None) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._recorder = recorder

    def register(self, tool: RegisteredTool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError("Tool registration is invalid.")
        self._tools[tool.name] = tool

    async def invoke(
        self,
        graph_name: str,
        tool_name: str,
        payload: dict[str, object],
        *,
        context: WorkflowContext | None = None,
        node_run_id: UUID | None = None,
        retry_count: int = 0,
    ) -> tuple[BaseModel, int]:
        """Invoke a registered tool and persist only its schema shape and outcome.

        Payloads and result values deliberately never reach the recorder.  Callers
        must pass a workflow context supplied by the server to add a trace row.
        """

        if retry_count < 0:
            raise ValueError("Tool retry count must be non-negative.")
        tool = self._tools.get(tool_name)
        if tool is None or graph_name not in tool.allowed_graphs:
            if tool is not None:
                await self._record(
                    context,
                    node_run_id=node_run_id,
                    tool=tool,
                    status="rejected",
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                    duration_ms=0,
                    retry_count=retry_count,
                    error_code="tool_not_allowed",
                )
            raise ControlledWorkflowError("tool_not_allowed")
        started_at = datetime.now(UTC)
        started = time.monotonic()
        try:
            parsed_input = tool.input_model.model_validate(payload)
            output = await tool.handler(parsed_input)
            validated = tool.output_model.model_validate(output)
        except ValidationError as error:
            duration_ms = max(0, int((time.monotonic() - started) * 1000))
            await self._record(
                context,
                node_run_id=node_run_id,
                tool=tool,
                status="rejected",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                duration_ms=duration_ms,
                retry_count=retry_count,
                error_code="tool_validation_failed",
            )
            raise ControlledWorkflowError("tool_validation_failed") from error
        except ControlledWorkflowError as error:
            duration_ms = max(0, int((time.monotonic() - started) * 1000))
            await self._record(
                context,
                node_run_id=node_run_id,
                tool=tool,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                duration_ms=duration_ms,
                retry_count=retry_count,
                error_code=error.code,
            )
            raise
        except Exception as error:
            duration_ms = max(0, int((time.monotonic() - started) * 1000))
            await self._record(
                context,
                node_run_id=node_run_id,
                tool=tool,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(UTC),
                duration_ms=duration_ms,
                retry_count=retry_count,
                error_code="tool_failed",
            )
            raise ControlledWorkflowError("tool_failed") from error
        duration_ms = max(0, int((time.monotonic() - started) * 1000))
        await self._record(
            context,
            node_run_id=node_run_id,
            tool=tool,
            status="succeeded",
            started_at=started_at,
            finished_at=datetime.now(UTC),
            duration_ms=duration_ms,
            retry_count=retry_count,
            error_code=None,
        )
        return validated, duration_ms

    async def _record(
        self,
        context: WorkflowContext | None,
        *,
        node_run_id: UUID | None,
        tool: RegisteredTool,
        status: str,
        started_at: datetime,
        finished_at: datetime,
        duration_ms: int,
        retry_count: int,
        error_code: str | None,
    ) -> None:
        if self._recorder is None or context is None:
            return
        await self._recorder.record_tool_call(
            context,
            node_run_id=node_run_id,
            tool_name=tool.name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            retry_count=retry_count,
            input_summary={"field_names": sorted(tool.input_model.model_fields)},
            output_summary={"field_names": sorted(tool.output_model.model_fields)},
            error_code=error_code,
        )
