"""Pure deterministic reciprocal-rank fusion and safe source presentation helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.services.retrieval.types import (
    MergedCandidate,
    PersistenceCandidate,
    RetrievalMethod,
    RetrievalWarningCode,
)

_METHOD_ORDER = (RetrievalMethod.SEMANTIC, RetrievalMethod.KEYWORD)


def merge_candidates(
    candidates: Iterable[PersistenceCandidate], *, fusion_constant: float
) -> tuple[MergedCandidate, ...]:
    """Deduplicate chunks with fixed RRF and stable document/chunk tie-breakers."""

    if fusion_constant <= 0:
        raise ValueError("fusion_constant must be positive")
    grouped: dict[object, list[PersistenceCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.chunk_id].append(candidate)

    merged: list[MergedCandidate] = []
    for entries in grouped.values():
        representative = min(
            entries,
            key=lambda item: (
                _METHOD_ORDER.index(item.method),
                item.method_rank,
                str(item.document_id),
                item.chunk_index,
                str(item.chunk_id),
            ),
        )
        methods = tuple(
            method for method in _METHOD_ORDER if any(item.method == method for item in entries)
        )
        score = sum(1.0 / (fusion_constant + item.method_rank) for item in entries)
        merged.append(
            MergedCandidate(
                candidate=representative,
                retrieval_methods=methods,
                rank_score=score,
            )
        )
    return tuple(
        sorted(
            merged,
            key=lambda item: (
                -item.rank_score,
                str(item.candidate.document_id),
                item.candidate.chunk_index,
                str(item.candidate.chunk_id),
            ),
        )
    )


def warning_codes_for_source_status(source_status: str) -> tuple[RetrievalWarningCode, ...]:
    """Map only governed non-approved source statuses to stable warnings."""

    warnings = {
        "draft": RetrievalWarningCode.SOURCE_DRAFT,
        "deprecated": RetrievalWarningCode.SOURCE_DEPRECATED,
        "restricted": RetrievalWarningCode.SOURCE_RESTRICTED,
        "archived": RetrievalWarningCode.SOURCE_ARCHIVED,
    }
    warning = warnings.get(source_status)
    return (warning,) if warning is not None else ()


def bounded_excerpt(content: str, *, maximum_characters: int) -> str:
    """Return a deterministic display excerpt that never exceeds the server cap."""

    if maximum_characters <= 0:
        raise ValueError("maximum_characters must be positive")
    normalized = " ".join(content.split())
    if len(normalized) <= maximum_characters:
        return normalized
    if maximum_characters == 1:
        return "…"
    return f"{normalized[: maximum_characters - 1].rstrip()}…"
