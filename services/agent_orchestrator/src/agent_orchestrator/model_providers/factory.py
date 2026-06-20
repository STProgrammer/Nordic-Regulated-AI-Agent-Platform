"""Server-owned construction of graph model providers."""

from __future__ import annotations

from collections.abc import Mapping

from agent_orchestrator.config import AgentSettings
from agent_orchestrator.model_providers.base import StructuredModelProvider
from agent_orchestrator.model_providers.deterministic import DeterministicModelProvider
from agent_orchestrator.model_providers.openai import OpenAIModelProvider


def build_model_provider(
    settings: AgentSettings,
    *,
    deterministic_fixtures: Mapping[str, Mapping[str, object]] | None = None,
) -> StructuredModelProvider:
    """Build the configured provider; fixture maps are accepted only for deterministic mode."""

    if settings.provider == "deterministic":
        return DeterministicModelProvider(deterministic_fixtures or {})
    return OpenAIModelProvider(settings)
