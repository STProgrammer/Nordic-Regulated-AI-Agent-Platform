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


class AnswerLanguage(StrEnum):
    """The two server-selected output languages supported by direct RAG answers."""

    NB = "nb"
    EN = "en"


class RagAnswerOutcome(StrEnum):
    """Public direct-answer outcomes; weak evidence is a normal result."""

    ANSWERED = "answered"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class RagEvidenceReason(StrEnum):
    """Content-free explanations for a normal RAG refusal."""

    NO_ELIGIBLE_SOURCES = "no_eligible_sources"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MODEL_REFUSED = "model_refused"
    CITATION_VALIDATION_FAILED = "citation_validation_failed"


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


@dataclass(frozen=True)
class RagAnswerCommand:
    """Trusted public-answer values after HTTP validation only."""

    case_id: UUID
    question: str
    answer_language: AnswerLanguage | None


@dataclass(frozen=True)
class AnswerEvidenceSource:
    """A run-local, approved evidence excerpt with a canonical citation label."""

    source: RetrievedSource
    citation_label: str
    excerpt: str


@dataclass(frozen=True)
class RagCitation:
    """The safe source view returned only for validated inline labels."""

    label: str
    document_id: UUID
    document_title: str
    document_file_type: str
    chunk_id: UUID
    page_number: int | None
    section_title: str | None
    excerpt: str
    rank: int
    retrieval_methods: tuple[RetrievalMethod, ...]


@dataclass(frozen=True)
class RagAnswerResult:
    """Service result mapped to the closed public answer response."""

    run_id: UUID
    outcome: RagAnswerOutcome
    language: AnswerLanguage
    answer: str
    citations: tuple[RagCitation, ...]
    evidence_reason: RagEvidenceReason | None
