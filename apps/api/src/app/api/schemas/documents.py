"""Typed public metadata views for secure document ingestion."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentSourceStatus(StrEnum):
    """Source-governance labels persisted at upload time."""

    APPROVED = "approved"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    RESTRICTED = "restricted"
    ARCHIVED = "archived"


class DocumentConfidentialityLevel(StrEnum):
    """Closed confidentiality labels; enforcement is owned by later retrieval phases."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DocumentParsingStatus(StrEnum):
    """Safe parser lifecycle state, never a raw worker task identifier."""

    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"


class DocumentIndexingStatus(StrEnum):
    """Safe lifecycle state for asynchronous chunking and embedding work."""

    NOT_READY = "not_ready"
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentData(BaseModel):
    """Safe created-document response with no content or storage implementation data."""

    model_config = ConfigDict(frozen=True)

    document_id: UUID
    case_id: UUID
    uploaded_by_user_id: UUID
    title: str
    original_filename: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    source_status: DocumentSourceStatus
    confidentiality_level: DocumentConfidentialityLevel
    parsing_status: DocumentParsingStatus
    language: str | None
    page_count: int | None
    parsing_error: str | None
    indexing_status: DocumentIndexingStatus
    indexing_error: str | None
    indexed_at: datetime | None
    inserted_at: datetime
    updated_at: datetime


class DocumentListData(BaseModel):
    """Stable, case-scoped page of safe document metadata."""

    model_config = ConfigDict(frozen=True)

    items: tuple[DocumentData, ...]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
    has_more: bool


class DocumentSourceStatusUpdateRequest(BaseModel):
    """The sole public governance mutation for a document in Phase 14."""

    model_config = ConfigDict(extra="forbid")

    source_status: DocumentSourceStatus


class DocumentSourceContextData(BaseModel):
    """A fixed, governed context view for one selected retrieval source chunk."""

    model_config = ConfigDict(frozen=True)

    document_id: UUID
    chunk_id: UUID
    document_title: str
    document_file_type: str
    source_status: DocumentSourceStatus
    page_number: int | None
    section_title: str | None
    context: str
    truncated: bool
