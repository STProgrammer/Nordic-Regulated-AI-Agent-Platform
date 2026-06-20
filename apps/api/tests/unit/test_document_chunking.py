"""Unit coverage for Phase 12 tokenizer-aware provenance preservation."""

from __future__ import annotations

from typing import cast

import pytest
from app.services.documents.chunking import (
    CanonicalTextChunker,
    ChunkingConfig,
    ChunkingError,
    TiktokenTokenizer,
)


def _chunker(*, maximum_tokens: int = 32, overlap_tokens: int = 4) -> CanonicalTextChunker:
    return CanonicalTextChunker(
        tokenizer=TiktokenTokenizer("cl100k_base"),
        config=ChunkingConfig(
            maximum_tokens=maximum_tokens,
            overlap_tokens=overlap_tokens,
            maximum_chunks=100,
            configuration_version="synthetic-v1",
            embedding_model="text-embedding-3-small",
        ),
    )


def test_chunker_preserves_trusted_page_section_and_offset_metadata() -> None:
    first = "Første avsnitt med policy REF-42."
    second = "Andre avsnitt med norsk kontrolltekst."
    text = f"{first}\n\n{second}"
    candidates = _chunker().build(
        extracted_text=text,
        extraction_metadata={
            "parser": {"name": "synthetic", "version": "1"},
            "language": {"value": "nb"},
            "locations": [
                {"start": 0, "end": len(first), "kind": "page", "page_number": 1},
                {
                    "start": len(first) + 2,
                    "end": len(text),
                    "kind": "section",
                    "label": "Kontroller",
                },
            ],
        },
        language="en",
    )

    assert [candidate.chunk_index for candidate in candidates] == [0, 1]
    assert [candidate.page_number for candidate in candidates] == [1, None]
    assert [candidate.section_title for candidate in candidates] == [None, "Kontroller"]
    assert [candidate.content for candidate in candidates] == [first, second]
    assert candidates[0].chunk_metadata["locations"] == [
        {"start": 0, "end": len(first), "kind": "page", "page_number": 1}
    ]
    assert candidates[1].chunk_metadata["parser"] == {"name": "synthetic", "version": "1"}
    assert candidates[1].chunk_metadata["language"] == "nb"
    for candidate in candidates:
        assert candidate.token_count == _chunker().tokenizer.count_tokens(candidate.content)
        assert "extracted_text" not in candidate.chunk_metadata


def test_chunker_hard_splits_long_trusted_span_with_bounded_token_counts() -> None:
    text = " ".join(f"policy-{number}" for number in range(80))
    chunker = _chunker(maximum_tokens=12, overlap_tokens=2)

    candidates = chunker.build(
        extracted_text=text,
        extraction_metadata={
            "locations": [{"start": 0, "end": len(text), "kind": "section", "label": "Long"}]
        },
        language="en",
    )

    assert len(candidates) > 2
    assert [candidate.chunk_index for candidate in candidates] == list(range(len(candidates)))
    assert all(0 < candidate.token_count <= 12 for candidate in candidates)
    assert all(
        candidate.chunk_metadata["locations"]
        == [{"start": 0, "end": len(text), "kind": "section", "label": "Long"}]
        for candidate in candidates
    )
    starts = [cast(int, candidate.chunk_metadata["char_start"]) for candidate in candidates]
    assert starts == sorted(starts)


@pytest.mark.parametrize(
    "locations",
    [
        [],
        [{"start": 1, "end": 1, "kind": "page"}],
        [{"start": 0, "end": 100, "kind": "page"}],
        [
            {"start": 0, "end": 4, "kind": "page"},
            {"start": 3, "end": 6, "kind": "page"},
        ],
    ],
)
def test_chunker_rejects_malformed_or_overlapping_parser_spans(locations: object) -> None:
    with pytest.raises(ChunkingError) as raised:
        _chunker().build(
            extracted_text="synthetic text",
            extraction_metadata={"locations": locations},
            language="en",
        )

    assert "synthetic text" not in str(raised.value)
