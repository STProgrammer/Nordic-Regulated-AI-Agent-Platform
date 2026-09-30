"""Provider-neutral structured completion contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from agent_orchestrator.prompts.base import EffectivePrompt
from agent_orchestrator.types import ModelUsage

OutputModel = TypeVar("OutputModel", bound=BaseModel)


class StructuredModelRequest(BaseModel):
    """A graph-built request; callers cannot choose providers or prompt text."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    operation: str = Field(min_length=1, max_length=100)
    prompt: EffectivePrompt
    input_payload: Mapping[str, object]
    output_model: type[BaseModel]


class ModelCompletion(BaseModel):
    """Validated structured output plus compact provider accounting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    output: dict[str, object]
    usage: ModelUsage


class StructuredModelProvider(Protocol):
    """Perform one structured completion with a provider selected by settings."""

    async def complete(self, request: StructuredModelRequest) -> ModelCompletion: ...
