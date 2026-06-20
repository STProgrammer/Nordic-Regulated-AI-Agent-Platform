"""Closed public request and safe source-result schemas for Phase 13 retrieval."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RetrievalSourceStatus(StrEnum):
    """Governed source labels accepted by the bounded public search input."""

    APPROVED = "approved"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    RESTRICTED = "restricted"
    ARCHIVED = "archived"


class RetrievalWarningCode(StrEnum):
    """Safe labels for source governance, not answer confidence or citations."""

    SOURCE_DRAFT = "source_draft"
    SOURCE_DEPRECATED = "source_deprecated"
    SOURCE_RESTRICTED = "source_restricted"
    SOURCE_ARCHIVED = "source_archived"


class RetrievalMethod(StrEnum):
    """The two independent Phase 13 candidate methods retained after fusion."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"


class RetrievalSearchRequest(BaseModel):
    """Disallow caller-owned tenant, vectors, candidate limits, SQL, and workflow ids."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: UUID
    query: str = Field(min_length=1, max_length=10_000)
    limit: int | None = Field(default=None, ge=1, le=100)
    source_statuses: tuple[RetrievalSourceStatus, ...] | None = Field(default=None, max_length=5)
    document_ids: tuple[UUID, ...] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _validate_unique_collections(self) -> RetrievalSearchRequest:
        if self.source_statuses is not None and len(set(self.source_statuses)) != len(
            self.source_statuses
        ):
            raise ValueError("source_statuses must not contain duplicates")
        if self.document_ids is not None and len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must not contain duplicates")
        return self


class RetrievalSourceData(BaseModel):
    """Bounded retrieval source view; deliberately omits raw chunks and citation labels."""

    model_config = ConfigDict(frozen=True)

    document_id: UUID
    document_title: str
    document_file_type: str
    chunk_id: UUID
    page_number: int | None
    section_title: str | None
    source_status: RetrievalSourceStatus
    rank: int = Field(ge=1)
    rank_score: float = Field(
        description="Deterministic reciprocal-rank-fusion signal; not confidence or faithfulness."
    )
    retrieval_methods: tuple[RetrievalMethod, ...]
    excerpt: str
    warning_codes: tuple[RetrievalWarningCode, ...]
