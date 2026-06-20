"""Tenant-aware, server-owned prompt resolution interfaces."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EffectivePrompt(BaseModel):
    """Prompt content and metadata returned only to trusted graph/model code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_id: UUID
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=100)
    organization_id: UUID | None
    content: str = Field(min_length=1)

    def safe_metadata(self) -> dict[str, str | None]:
        """Return persistence-safe metadata without leaking prompt content."""

        return {"prompt_id": str(self.prompt_id), "name": self.name, "version": self.version}


class PromptLoader(Protocol):
    """Resolve only server-selected active prompts for one organization."""

    async def load_active(self, organization_id: UUID, prompt_name: str) -> EffectivePrompt: ...
