from __future__ import annotations

from uuid import uuid4

from app.services.retrieval.citations import citations_for_labels, validate_inline_citations
from app.services.retrieval.types import (
    AnswerEvidenceSource,
    RetrievalMethod,
    RetrievedSource,
)


def _evidence() -> tuple[AnswerEvidenceSource, ...]:
    source = RetrievedSource(
        document_id=uuid4(),
        document_title="Synthetic policy",
        document_file_type="txt",
        chunk_id=uuid4(),
        page_number=2,
        section_title="Terms",
        source_status="approved",
        rank=1,
        rank_score=0.03,
        retrieval_methods=(RetrievalMethod.SEMANTIC, RetrievalMethod.KEYWORD),
        excerpt="Synthetic supporting text.",
        warning_codes=(),
    )
    return (AnswerEvidenceSource(source=source, citation_label="S1", excerpt=source.excerpt),)


def test_valid_inline_citation_shapes_only_safe_source_data() -> None:
    evidence = _evidence()

    validation = validate_inline_citations(
        "The synthetic policy applies. [S1]", evidence, maximum_answer_characters=100
    )
    citations = citations_for_labels(validation.labels, evidence)

    assert validation.is_valid is True
    assert citations[0].label == "S1"
    assert citations[0].rank == 1
    assert not hasattr(citations[0], "rank_score")


def test_invalid_duplicate_unknown_malformed_or_missing_citations_are_suppressed() -> None:
    evidence = _evidence()
    for answer in (
        "No citation.",
        "Duplicate labels. [S1] [S1]",
        "Unknown source. [S2]",
        "Malformed source. [S01]",
        "Malformed source. [Sx]",
        "Too long " + "x" * 100,
    ):
        validation = validate_inline_citations(answer, evidence, maximum_answer_characters=100)
        assert validation.is_valid is False
