"""Pure preliminary evidence selection for the direct RAG answer boundary."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.retrieval.types import AnswerEvidenceSource, RagEvidenceReason, RetrievedSource


@dataclass(frozen=True)
class EvidenceAssessment:
    """A deterministic threshold result, intentionally not a confidence score."""

    is_sufficient: bool
    reason: RagEvidenceReason | None
    sources: tuple[AnswerEvidenceSource, ...]
    source_count: int
    excerpt_characters: int


def select_answer_evidence(
    sources: tuple[RetrievedSource, ...],
    *,
    maximum_sources: int,
    maximum_characters: int,
) -> tuple[AnswerEvidenceSource, ...]:
    """Assign stable labels and apply server-owned rank-order context budgets.

    Retrieval has already bounded every excerpt.  The final source may be clipped
    further to fit the answer-context ceiling; no raw text is fetched here.
    """

    if maximum_sources <= 0 or maximum_characters <= 0:
        raise ValueError("Evidence limits must be positive.")
    selected: list[AnswerEvidenceSource] = []
    remaining = maximum_characters
    ordered_sources = tuple(
        sorted(
            sources,
            key=lambda source: (source.rank, source.document_id.hex, source.chunk_id.hex),
        )
    )
    for source in ordered_sources[:maximum_sources]:
        if source.source_status != "approved":
            raise ValueError("Direct RAG evidence must be approved.")
        if source.rank < 1 or not source.excerpt:
            raise ValueError("Direct RAG evidence is internally inconsistent.")
        if remaining <= 0:
            break
        excerpt = source.excerpt[:remaining]
        if not excerpt:
            break
        selected.append(
            AnswerEvidenceSource(
                source=source,
                citation_label=f"S{len(selected) + 1}",
                excerpt=excerpt,
            )
        )
        remaining -= len(excerpt)
    return tuple(selected)


def assess_evidence(
    sources: tuple[AnswerEvidenceSource, ...],
    *,
    minimum_sources: int,
    minimum_excerpt_characters: int,
) -> EvidenceAssessment:
    """Apply only the Phase-15 preliminary count/character safeguards."""

    if minimum_sources <= 0 or minimum_excerpt_characters <= 0:
        raise ValueError("Evidence thresholds must be positive.")
    source_count = len(sources)
    excerpt_characters = sum(len(source.excerpt) for source in sources)
    if source_count == 0:
        return EvidenceAssessment(
            is_sufficient=False,
            reason=RagEvidenceReason.NO_ELIGIBLE_SOURCES,
            sources=sources,
            source_count=source_count,
            excerpt_characters=excerpt_characters,
        )
    if source_count < minimum_sources or excerpt_characters < minimum_excerpt_characters:
        return EvidenceAssessment(
            is_sufficient=False,
            reason=RagEvidenceReason.INSUFFICIENT_EVIDENCE,
            sources=sources,
            source_count=source_count,
            excerpt_characters=excerpt_characters,
        )
    return EvidenceAssessment(
        is_sufficient=True,
        reason=None,
        sources=sources,
        source_count=source_count,
        excerpt_characters=excerpt_characters,
    )
