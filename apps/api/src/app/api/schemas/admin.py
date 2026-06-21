"""Strict controlled-memory Admin request and response contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from agent_orchestrator.memory.policy import MemoryOrigin, MemoryScope, MemoryType
from pydantic import BaseModel, ConfigDict, Field


class MemorySettingsData(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool


class MemorySettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class OrganizationMemoryEntryCreateRequest(BaseModel):
    """The service validates the closed type-specific object before persistence."""

    model_config = ConfigDict(extra="forbid")

    memory_type: MemoryType
    content: dict[str, object] = Field(min_length=1, max_length=4)


class OrganizationMemoryEntryRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: dict[str, object] = Field(min_length=1, max_length=4)


class MemoryEntryData(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_entry_id: UUID
    memory_scope: MemoryScope
    memory_type: MemoryType
    content: dict[str, object]
    source: MemoryOrigin
    is_active: bool
    archived_at: datetime | None
    inserted_at: datetime
    updated_at: datetime


class MemoryEntryListData(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[MemoryEntryData, ...]
