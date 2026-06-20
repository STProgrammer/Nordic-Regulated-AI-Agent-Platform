"""Validated agent-specific configuration, isolated from direct RAG settings."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AgentProviderName = Literal["openai", "azure_openai", "deterministic"]
Environment = Literal["local", "test", "staging", "production"]


class AgentSettings(BaseSettings):
    """Configuration for graph-owned model calls, never controlled by HTTP input."""

    model_config = SettingsConfigDict(
        env_prefix="NORDIC_AGENT_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    environment: Environment = "local"
    provider: AgentProviderName = "deterministic"
    model: str = "gpt-4.1-mini"
    api_key: SecretStr | None = None
    azure_endpoint: SecretStr | None = None
    azure_api_version: str = "2024-02-01"
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    max_output_tokens: int = Field(default=800, ge=1, le=8192)
    node_maximum_retries: int = Field(default=1, ge=0, le=5)
    snapshot_max_codes: int = Field(default=12, ge=1, le=32)
    intake_confidence_threshold: float = Field(default=0.8, ge=0.5, le=1.0)
    evidence_maximum_sources: int = Field(default=5, ge=1, le=20)
    evidence_maximum_excerpt_characters: int = Field(default=5_000, ge=64, le=20_000)
    evidence_minimum_sources: int = Field(default=1, ge=1, le=20)
    evidence_minimum_excerpt_characters: int = Field(default=200, ge=1, le=20_000)
    extraction_confidence_threshold: float = Field(default=0.8, ge=0.5, le=1.0)

    @field_validator("model", "azure_api_version")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be blank")
        return trimmed

    @model_validator(mode="after")
    def _validate_provider(self) -> AgentSettings:
        if self.evidence_minimum_sources > self.evidence_maximum_sources:
            raise ValueError("evidence minimum sources must not exceed maximum sources")
        if self.evidence_minimum_excerpt_characters > self.evidence_maximum_excerpt_characters:
            raise ValueError("evidence minimum excerpt characters must not exceed the maximum")
        if self.provider == "deterministic" and self.environment not in {"local", "test"}:
            raise ValueError("deterministic agent provider is permitted only in local or test")
        if self.environment in {"staging", "production"} and self.api_key is None:
            raise ValueError("agent API credentials are required outside local and test")
        if self.provider == "azure_openai" and self.azure_endpoint is None:
            raise ValueError("Azure agent endpoint is required for azure_openai")
        return self
