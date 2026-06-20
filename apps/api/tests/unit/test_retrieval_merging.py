from __future__ import annotations

from uuid import UUID

from app.services.retrieval.merging import (
    bounded_excerpt,
    merge_candidates,
    warning_codes_for_source_status,
)
from app.services.retrieval.types import PersistenceCandidate, RetrievalMethod, RetrievalWarningCode


def _candidate(
    *,
    chunk_id: str,
    method: RetrievalMethod,
    rank: int,
    document_id: str = "00000000-0000-0000-0000-000000000001",
    chunk_index: int = 0,
) -> PersistenceCandidate:
    return PersistenceCandidate(
        chunk_id=UUID(chunk_id),
        document_id=UUID(document_id),
        document_title="Synthetic policy",
        document_file_type="txt",
        chunk_index=chunk_index,
        page_number=None,
        section_title=None,
        source_status="approved",
        excerpt_content="Synthetic controlled source excerpt.",
        method=method,
        method_rank=rank,
    )


def test_rrf_deduplicates_overlapping_chunks_and_retains_methods() -> None:
    overlap = "00000000-0000-0000-0000-000000000010"
    semantic_only = "00000000-0000-0000-0000-000000000011"
    merged = merge_candidates(
        (
            _candidate(chunk_id=overlap, method=RetrievalMethod.SEMANTIC, rank=1),
            _candidate(chunk_id=semantic_only, method=RetrievalMethod.SEMANTIC, rank=2),
            _candidate(chunk_id=overlap, method=RetrievalMethod.KEYWORD, rank=1),
        ),
        fusion_constant=60,
    )

    assert [item.candidate.chunk_id for item in merged] == [UUID(overlap), UUID(semantic_only)]
    assert merged[0].retrieval_methods == (RetrievalMethod.SEMANTIC, RetrievalMethod.KEYWORD)
    assert merged[0].rank_score == 2 / 61


def test_result_helpers_bound_excerpts_and_emit_only_source_status_warnings() -> None:
    assert bounded_excerpt("a  b   c", maximum_characters=4) == "a b…"
    assert warning_codes_for_source_status("approved") == ()
    assert warning_codes_for_source_status("deprecated") == (
        RetrievalWarningCode.SOURCE_DEPRECATED,
    )
