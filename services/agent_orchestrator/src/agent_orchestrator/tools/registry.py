"""Typed registry that prevents graph state from selecting arbitrary tools."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from agent_orchestrator.errors import ControlledWorkflowError

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

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError("Tool registration is invalid.")
        self._tools[tool.name] = tool

    async def invoke(
        self, graph_name: str, tool_name: str, payload: dict[str, object]
    ) -> tuple[BaseModel, int]:
        tool = self._tools.get(tool_name)
        if tool is None or graph_name not in tool.allowed_graphs:
            raise ControlledWorkflowError("tool_not_allowed")
        started = time.monotonic()
        try:
            parsed_input = tool.input_model.model_validate(payload)
            output = await tool.handler(parsed_input)
            validated = tool.output_model.model_validate(output)
        except ControlledWorkflowError:
            raise
        except Exception as error:
            raise ControlledWorkflowError("tool_failed") from error
        return validated, max(0, int((time.monotonic() - started) * 1000))
