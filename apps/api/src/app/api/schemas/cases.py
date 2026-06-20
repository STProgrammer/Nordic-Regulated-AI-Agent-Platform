"""Typed public request and response models for Case Management."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CaseStatus(StrEnum):
    """Closed lifecycle values persisted by the Case Management service."""

    NEW = "new"
    PROCESSING = "processing"
    WAITING_FOR_HUMAN_REVIEW = "waiting_for_human_review"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class CasePriority(StrEnum):
    """The initial, product-defined priority values."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class CaseDomain(StrEnum):
    """The fixed domain packs available before organization configuration exists."""

    PUBLIC_SECTOR = "public_sector"
    BANKING_COMPLIANCE = "banking_compliance"
    ENERGY_OPERATIONS = "energy_operations"
    INTERNAL_POLICY = "internal_policy"


class CaseLanguage(StrEnum):
    """Languages accepted by the initial Case Management contract."""

    NORWEGIAN_BOKMAL = "nb"
    ENGLISH = "en"


class CaseRiskLevel(StrEnum):
    """Future workflow-assigned risk values accepted only as list filters here."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _meaningful(value: str) -> str:
    """Trim a user-facing string and reject whitespace-only input."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError("This field must not be empty.")
    return trimmed


class CaseCreateRequest(BaseModel):
    """The small caller-controlled input for submitting a new case."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)
    domain: CaseDomain
    priority: CasePriority
    language: CaseLanguage
    due_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=255)

    @field_validator("title", "description")
    @classmethod
    def _normalize_required_content(cls, value: str) -> str:
        return _meaningful(value)

    @field_validator("external_reference")
    @classmethod
    def _normalize_optional_reference(cls, value: str | None) -> str | None:
        return _meaningful(value) if value is not None else None


class CaseUpdateRequest(BaseModel):
    """An explicitly non-empty patch while preserving intentional null clears."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1, max_length=20_000)
    domain: CaseDomain | None = None
    priority: CasePriority | None = None
    language: CaseLanguage | None = None
    due_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=255)
    assigned_user_id: UUID | None = None
    status: CaseStatus | None = None

    @field_validator("title", "description", "external_reference")
    @classmethod
    def _normalize_optional_content(cls, value: str | None) -> str | None:
        return _meaningful(value) if value is not None else None

    @model_validator(mode="after")
    def _validate_requested_fields(self) -> CaseUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("At least one mutable field is required.")
        non_clearable = {
            "title",
            "description",
            "domain",
            "priority",
            "language",
            "status",
        }
        for field_name in non_clearable & self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null.")
        return self


class CaseData(BaseModel):
    """Complete safe case representation for submit, detail, patch, and archive."""

    model_config = ConfigDict(frozen=True)

    case_id: UUID
    case_number: str
    title: str
    description: str
    language: CaseLanguage
    domain: CaseDomain
    case_type: str | None
    priority: CasePriority
    status: CaseStatus
    risk_level: CaseRiskLevel | None
    assigned_user_id: UUID | None
    submitted_by_user_id: UUID
    due_date: date | None
    external_reference: str | None
    inserted_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class CaseSummaryData(BaseModel):
    """List-safe case data without the full description/reference business content."""

    model_config = ConfigDict(frozen=True)

    case_id: UUID
    case_number: str
    title: str
    language: CaseLanguage
    domain: CaseDomain
    priority: CasePriority
    status: CaseStatus
    risk_level: CaseRiskLevel | None
    assigned_user_id: UUID | None
    submitted_by_user_id: UUID
    due_date: date | None
    inserted_at: datetime
    updated_at: datetime


class CaseListData(BaseModel):
    """A stable offset page for the Case Inbox consumer delivered in Phase 9."""

    model_config = ConfigDict(frozen=True)

    items: tuple[CaseSummaryData, ...]
    limit: int
    offset: int
    total: int
    has_more: bool


class CaseAssigneeOptionData(BaseModel):
    """The smallest identity view needed to filter visible Case Inbox results.

    This deliberately is not a user-directory model.  It is available only
    when an active, non-archived case in the current organization is assigned
    to the user represented by this option.
    """

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    display_name: str


class CaseAssigneeListData(BaseModel):
    """Tenant-scoped choices for the Case Inbox assignee filter."""

    model_config = ConfigDict(frozen=True)

    items: tuple[CaseAssigneeOptionData, ...]
