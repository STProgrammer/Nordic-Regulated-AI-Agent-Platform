"""Fixture-only deterministic provider used for local and automated tests."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from agent_orchestrator.errors import InvalidModelOutputError, ProviderUnavailableError
from agent_orchestrator.model_providers.base import ModelCompletion, StructuredModelRequest
from agent_orchestrator.observability import get_agent_telemetry
from agent_orchestrator.types import ModelUsage


class DeterministicModelProvider:
    """Return fixture output keyed solely by the server-owned operation name."""

    provider_label = "deterministic"
    model_label = "deterministic-fixture-v1"

    def __init__(self, fixtures: Mapping[str, Mapping[str, object]]) -> None:
        self._fixtures = dict(fixtures)

    async def complete(self, request: StructuredModelRequest) -> ModelCompletion:
        fixture = self._fixtures.get(request.operation)
        if fixture is None:
            get_agent_telemetry().model(
                provider=self.provider_label,
                model=self.model_label,
                operation=request.operation,
                outcome="failure",
                latency_ms=0,
            )
            raise ProviderUnavailableError()
        try:
            output = request.output_model.model_validate(dict(fixture)).model_dump(mode="json")
        except ValidationError as error:
            get_agent_telemetry().model(
                provider=self.provider_label,
                model=self.model_label,
                operation=request.operation,
                outcome="failure",
                latency_ms=0,
            )
            raise InvalidModelOutputError() from error
        result = ModelCompletion(
            output=output,
            usage=ModelUsage(
                provider=self.provider_label,
                model_name=self.model_label,
                operation=request.operation,
                latency_ms=0,
                token_input=None,
                token_output=None,
                success=True,
            ),
        )
        get_agent_telemetry().model(
            provider=result.usage.provider,
            model=result.usage.model_name,
            operation=result.usage.operation,
            outcome="success",
            latency_ms=result.usage.latency_ms,
            token_input=result.usage.token_input,
            token_output=result.usage.token_output,
        )
        return result
