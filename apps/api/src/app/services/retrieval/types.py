"""Typed values crossing the Phase 13 retrieval service boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class RetrievalMethod(StrEnum):
    """Independent bounded retrieval methods, in deterministic public order."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"


class RetrievalWarningCode(StrEnum):
    """Stable source-governance labels; these are not evidence decisions."""

    SOURCE_DRAFT = "source_draft"
    SOURCE_DEPRECATED = "source_deprecated"
    SOURCE_RESTRICTED = "source_restricted"
    SOURCE_ARCHIVED = "source_archived"


@dataclass(frozen=True)
class RetrievalRequest:
    """Trusted public-search values after transport validation only."""

    case_id: UUID
    query: str
    result_limit: int | None
    source_statuses: tuple[str, ...]
    document_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class RetrievalWorkflowContext:
    """Future-only verified workflow linkage; public HTTP never supplies this."""

    workflow_run_id: UUID


@dataclass(frozen=True)
class RewrittenQuery:
    """Exact normalized forms, with intentionally no expansion or translation."""

    semantic_query: str
    full_text_query: str | None


@dataclass(frozen=True)
class RetrievalScope:
    """Resolved organization and source-governance filters for both SQL queries."""

    organization_id: UUID
    source_statuses: tuple[str, ...]
    document_ids: tuple[UUID, ...]
    restricted_entitled: bool


@dataclass(frozen=True)
class PersistenceCandidate:
    """Minimal, SQL-filtered candidate data; no vectors or document storage data."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    document_file_type: str
    chunk_index: int
    page_number: int | None
    section_title: str | None
    source_status: str
    excerpt_content: str
    method: RetrievalMethod
    method_rank: int


@dataclass(frozen=True)
class MergedCandidate:
    """One deduplicated candidate carrying only deterministic rank signals."""

    candidate: PersistenceCandidate
    retrieval_methods: tuple[RetrievalMethod, ...]
    rank_score: float


@dataclass(frozen=True)
class RetrievedSource:
    """The safe internal source view mapped to the public response schema."""

    document_id: UUID
    document_title: str
    document_file_type: str
    chunk_id: UUID
    page_number: int | None
    section_title: str | None
    source_status: str
    rank: int
    rank_score: float
    retrieval_methods: tuple[RetrievalMethod, ...]
    excerpt: str
    warning_codes: tuple[RetrievalWarningCode, ...]
