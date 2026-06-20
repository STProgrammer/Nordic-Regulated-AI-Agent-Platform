from __future__ import annotations

from uuid import uuid4

import pytest
from app.services.retrieval.evidence import assess_evidence, select_answer_evidence
from app.services.retrieval.types import RetrievalMethod, RetrievedSource


def _source(
    *, rank: int = 1, status: str = "approved", excerpt: str = "Synthetic evidence."
) -> RetrievedSource:
    return RetrievedSource(
        document_id=uuid4(),
        document_title="Synthetic policy",
        document_file_type="txt",
        chunk_id=uuid4(),
        page_number=1,
        section_title="Scope",
        source_status=status,
        rank=rank,
        rank_score=0.03,
        retrieval_methods=(RetrievalMethod.SEMANTIC,),
        excerpt=excerpt,
        warning_codes=(),
    )


def test_evidence_is_rank_ordered_labeled_and_clipped_under_server_budget() -> None:
    second = _source(rank=2, excerpt="abcdef")
    first = _source(rank=1, excerpt="abcdef")

    selected = select_answer_evidence((second, first), maximum_sources=2, maximum_characters=8)

    assert [item.citation_label for item in selected] == ["S1", "S2"]
    assert [item.source.rank for item in selected] == [1, 2]
    assert [item.excerpt for item in selected] == ["abcdef", "ab"]


def test_preliminary_evidence_policy_is_counts_and_characters_not_rank_score() -> None:
    selected = select_answer_evidence(
        (_source(excerpt="a" * 10),), maximum_sources=2, maximum_characters=50
    )
    insufficient = assess_evidence(selected, minimum_sources=2, minimum_excerpt_characters=5)
    no_sources = assess_evidence((), minimum_sources=1, minimum_excerpt_characters=1)

    assert insufficient.is_sufficient is False
    assert insufficient.reason is not None
    assert no_sources.reason is not None


def test_non_approved_or_invalid_evidence_is_never_selected() -> None:
    with pytest.raises(ValueError):
        select_answer_evidence(
            (_source(status="restricted"),), maximum_sources=1, maximum_characters=20
        )
    with pytest.raises(ValueError):
        select_answer_evidence((_source(rank=0),), maximum_sources=1, maximum_characters=20)
