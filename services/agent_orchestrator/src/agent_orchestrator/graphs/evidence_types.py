"""Closed state and value vocabulary for the Phase-18 Evidence graph."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agent_orchestrator.state.case_state import CaseWorkflowState


class EvidenceOutcome(StrEnum):
    """The only normal terminal Evidence outcomes."""

    COMPLETED = "completed"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class EvidenceReason(StrEnum):
    """Content-free reasons that are safe in status and audit projections."""

    NO_ELIGIBLE_SOURCES = "no_eligible_sources"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"


class EvidencePresentationSource(BaseModel):
    """Identifier-only source presentation metadata; it deliberately has no excerpt or score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    citation_label: Annotated[str, Field(pattern=r"^S[1-9][0-9]*$", max_length=16)]
    document_id: UUID
    chunk_id: UUID
    source_status: str = "approved"
    warning_codes: tuple[str, ...] = Field(default=(), max_length=4)


class EvidenceWorkflowState(CaseWorkflowState):
    """Durable Evidence signals only; queries, case text, excerpts, and scores stay transient."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_outcome: EvidenceOutcome | None = None
    node_count: Annotated[int, Field(ge=0, le=10)] = 0
    vector_candidate_count: Annotated[int, Field(ge=0, le=500)] = 0
    keyword_candidate_count: Annotated[int, Field(ge=0, le=500)] = 0
    merged_candidate_count: Annotated[int, Field(ge=0, le=500)] = 0
    reranked_source_count: Annotated[int, Field(ge=0, le=50)] = 0
    permitted_source_count: Annotated[int, Field(ge=0, le=50)] = 0
    approved_source_count: Annotated[int, Field(ge=0, le=50)] = 0
    evidence_source_count: Annotated[int, Field(ge=0, le=20)] = 0
    evidence_sufficient: bool = False
    contradiction_detected: bool = False
    citation_labels: tuple[str, ...] = Field(default=(), max_length=20)
    evidence_sources: tuple[EvidencePresentationSource, ...] = Field(default=(), max_length=20)
    reason_codes: tuple[EvidenceReason, ...] = Field(default=(), max_length=3)
