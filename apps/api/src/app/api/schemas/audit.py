"""Read-only, safe audit inspection contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEventData(BaseModel):
    """One sanitized immutable audit event, excluding transport and raw metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID
    event_type: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: UUID | None
    case_id: UUID | None
    actor_user_id: UUID | None
    inserted_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)


class AuditEventListData(BaseModel):
    """A bounded deterministic page of current-tenant audit events."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[AuditEventData, ...]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
    has_more: bool
