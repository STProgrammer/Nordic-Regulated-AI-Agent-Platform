"""Pure run-local citation helpers for source-grounded RAG answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.retrieval.types import AnswerEvidenceSource, RagCitation

_VALID_LABEL = re.compile(r"\[S([1-9][0-9]*)\]")
_POSSIBLE_LABEL = re.compile(r"\[S[^\]]*\]")


@dataclass(frozen=True)
class CitationValidation:
    """Structural citation validation only; it does not claim semantic entailment."""

    is_valid: bool
    labels: tuple[str, ...]


def validate_inline_citations(
    answer: str,
    evidence: tuple[AnswerEvidenceSource, ...],
    *,
    maximum_answer_characters: int,
) -> CitationValidation:
    """Require exact, unique, source-owned labels before publishing an answer."""

    if not answer.strip() or len(answer) > maximum_answer_characters:
        return CitationValidation(False, ())
    labels = tuple(f"S{match}" for match in _VALID_LABEL.findall(answer))
    possible_labels = tuple(_POSSIBLE_LABEL.findall(answer))
    if not labels or len(labels) != len(set(labels)):
        return CitationValidation(False, ())
    if len(possible_labels) != len(labels):
        return CitationValidation(False, ())
    allowed = {source.citation_label for source in evidence}
    if any(label not in allowed for label in labels):
        return CitationValidation(False, ())
    return CitationValidation(True, labels)


def citations_for_labels(
    labels: tuple[str, ...], evidence: tuple[AnswerEvidenceSource, ...]
) -> tuple[RagCitation, ...]:
    """Map validated labels to the deliberately narrow citation response shape."""

    by_label = {source.citation_label: source for source in evidence}
    return tuple(
        RagCitation(
            label=label,
            document_id=by_label[label].source.document_id,
            document_title=by_label[label].source.document_title,
            document_file_type=by_label[label].source.document_file_type,
            chunk_id=by_label[label].source.chunk_id,
            page_number=by_label[label].source.page_number,
            section_title=by_label[label].source.section_title,
            excerpt=by_label[label].excerpt,
            rank=by_label[label].source.rank,
            retrieval_methods=by_label[label].source.retrieval_methods,
        )
        for label in labels
    )
