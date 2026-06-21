"""Lazy official-SDK provider adapters for OpenAI-compatible structured output."""

from __future__ import annotations

import json
import time
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI
from pydantic import ValidationError

from agent_orchestrator.config import AgentSettings
from agent_orchestrator.errors import InvalidModelOutputError, ProviderUnavailableError
from agent_orchestrator.model_providers.base import ModelCompletion, StructuredModelRequest
from agent_orchestrator.observability import get_agent_telemetry
from agent_orchestrator.types import ModelUsage


class OpenAIModelProvider:
    """Use a lazily constructed official client; runtime retries remain graph-owned."""

    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        self._client: AsyncOpenAI | AsyncAzureOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI | AsyncAzureOpenAI:
        if self._client is not None:
            return self._client
        api_key = self._settings.api_key
        if api_key is None:
            raise ProviderUnavailableError()
        if self._settings.provider == "azure_openai":
            endpoint = self._settings.azure_endpoint
            if endpoint is None:
                raise ProviderUnavailableError()
            self._client = AsyncAzureOpenAI(
                api_key=api_key.get_secret_value(),
                azure_endpoint=endpoint.get_secret_value(),
                api_version=self._settings.azure_api_version,
                max_retries=0,
                timeout=self._settings.timeout_seconds,
            )
        else:
            self._client = AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                max_retries=0,
                timeout=self._settings.timeout_seconds,
            )
        return self._client

    async def complete(self, request: StructuredModelRequest) -> ModelCompletion:
        started = time.monotonic()
        try:
            with get_agent_telemetry().span(
                "model.request", {"model.operation": request.operation}
            ):
                completion: Any = await self._get_client().chat.completions.create(
                    model=self._settings.model,
                    messages=[
                        {"role": "system", "content": request.prompt.content},
                        {"role": "user", "content": json.dumps(dict(request.input_payload))},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=self._settings.max_output_tokens,
                )
            content = completion.choices[0].message.content
            if not isinstance(content, str):
                raise InvalidModelOutputError()
            output = request.output_model.model_validate_json(content).model_dump(mode="json")
        except InvalidModelOutputError:
            _record_failure(request, self._settings, started)
            raise
        except (IndexError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as error:
            _record_failure(request, self._settings, started)
            raise InvalidModelOutputError() from error
        except Exception as error:
            _record_failure(request, self._settings, started)
            raise ProviderUnavailableError() from error
        usage = getattr(completion, "usage", None)
        result = ModelCompletion(
            output=output,
            usage=ModelUsage(
                provider=self._settings.provider,
                model_name=self._settings.model,
                operation=request.operation,
                latency_ms=max(0, int((time.monotonic() - started) * 1000)),
                token_input=_usage_value(usage, "prompt_tokens"),
                token_output=_usage_value(usage, "completion_tokens"),
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


def _usage_value(usage: object, field: str) -> int | None:
    value = getattr(usage, field, None)
    return value if isinstance(value, int) and value >= 0 else None


def _record_failure(
    request: StructuredModelRequest, settings: AgentSettings, started: float
) -> None:
    get_agent_telemetry().model(
        provider=settings.provider,
        model=settings.model,
        operation=request.operation,
        outcome="failure",
        latency_ms=max(0, int((time.monotonic() - started) * 1000)),
    )
