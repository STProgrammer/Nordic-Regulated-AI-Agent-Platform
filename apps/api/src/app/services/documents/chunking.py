"""Tokenizer-aware, provenance-preserving canonical-text chunking.

This module receives only the already-validated Phase 11 canonical text and its
location metadata. It never reads raw object storage and never logs content.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from tiktoken import Encoding, get_encoding

_SAFE_FAILURE_SUMMARY = "Document text cannot be indexed safely."
_NATURAL_BOUNDARY = re.compile(r"\n{2,}|(?<=[.!?])\s+|\s+")


class ChunkingError(Exception):
    """A permanent safe chunking failure with no source text in its message."""

    def __init__(self) -> None:
        super().__init__(_SAFE_FAILURE_SUMMARY)

    @property
    def summary(self) -> str:
        return _SAFE_FAILURE_SUMMARY


class Tokenizer(Protocol):
    """Small tokenizer boundary so unit tests can use deterministic fakes."""

    def count_tokens(self, value: str) -> int:
        """Return the token count for exactly ``value``."""


class TiktokenTokenizer:
    """Tokenizer selected explicitly by embedding-compatible encoding name."""

    def __init__(self, encoding_name: str) -> None:
        try:
            self._encoding: Encoding = get_encoding(encoding_name)
        except Exception as error:
            raise ChunkingError() from error
        self.label = encoding_name

    def count_tokens(self, value: str) -> int:
        try:
            return len(self._encoding.encode(value, disallowed_special=()))
        except Exception as error:
            raise ChunkingError() from error


@dataclass(frozen=True)
class ChunkingConfig:
    """Validated immutable chunk policy measured in selected tokenizer tokens."""

    maximum_tokens: int
    overlap_tokens: int
    maximum_chunks: int
    configuration_version: str
    embedding_model: str

    def __post_init__(self) -> None:
        if (
            self.maximum_tokens <= 0
            or self.overlap_tokens < 0
            or self.overlap_tokens >= self.maximum_tokens
            or self.maximum_chunks <= 0
            or not self.configuration_version.strip()
            or not self.embedding_model.strip()
        ):
            raise ValueError("Invalid document chunking configuration")


@dataclass(frozen=True)
class TrustedLocationSpan:
    """Validated Phase 11 source span, retaining only citation-safe labels."""

    start: int
    end: int
    kind: str
    label: str | None
    page_number: int | None

    def as_metadata(self) -> dict[str, int | str]:
        value: dict[str, int | str] = {"start": self.start, "end": self.end, "kind": self.kind}
        if self.label is not None:
            value["label"] = self.label
        if self.page_number is not None:
            value["page_number"] = self.page_number
        return value


@dataclass(frozen=True)
class ChunkCandidate:
    """A fully validated candidate before it is sent to an embedding provider."""

    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    token_count: int
    chunk_metadata: dict[str, object]


class CanonicalTextChunker:
    """Split trusted spans without crossing provenance boundaries or leaking text."""

    def __init__(self, *, tokenizer: Tokenizer, config: ChunkingConfig) -> None:
        self.tokenizer = tokenizer
        self.config = config

    def build(
        self,
        *,
        extracted_text: str,
        extraction_metadata: Mapping[str, object],
        language: str | None,
    ) -> tuple[ChunkCandidate, ...]:
        """Build stable chunk candidates from one canonical text record.

        Phase 11 spans are deliberately validated before any source labels are
        persisted again. Invalid historical metadata therefore fails safe rather
        than inventing a page or section citation.
        """

        spans = _trusted_spans(extracted_text, extraction_metadata)
        parser_metadata = _parser_metadata(extraction_metadata)
        resolved_language = _resolved_language(extraction_metadata, language)
        candidates: list[ChunkCandidate] = []
        for span in spans:
            span_candidates = self._chunk_span(
                extracted_text,
                span,
                initial_index=len(candidates),
                parser_metadata=parser_metadata,
                language=resolved_language,
            )
            candidates.extend(span_candidates)
            if len(candidates) > self.config.maximum_chunks:
                raise ChunkingError()
        if not candidates:
            raise ChunkingError()
        self._validate_candidates(candidates, extracted_text)
        return tuple(candidates)

    def _chunk_span(
        self,
        extracted_text: str,
        span: TrustedLocationSpan,
        *,
        initial_index: int,
        parser_metadata: dict[str, str] | None,
        language: str | None,
    ) -> list[ChunkCandidate]:
        span_end = _trim_right(extracted_text, span.start, span.end)
        cursor = _trim_left(extracted_text, span.start, span_end)
        if cursor >= span_end:
            return []
        values: list[ChunkCandidate] = []
        while cursor < span_end:
            hard_end = self._hard_end(extracted_text, cursor, span_end)
            split_at = self._natural_end(extracted_text, cursor, hard_end, span_end)
            # A very early natural boundary would cause the requested overlap to
            # cover the whole candidate. Use a deterministic hard split instead
            # so each iteration must advance.
            split_tokens = self.tokenizer.count_tokens(extracted_text[cursor:split_at])
            if split_at < span_end and split_tokens <= self.config.overlap_tokens:
                split_at = hard_end
            content_end = _trim_right(extracted_text, cursor, split_at)
            if content_end <= cursor:
                raise ChunkingError()
            content = extracted_text[cursor:content_end]
            token_count = self.tokenizer.count_tokens(content)
            if token_count <= 0 or token_count > self.config.maximum_tokens:
                raise ChunkingError()
            values.append(
                ChunkCandidate(
                    chunk_index=initial_index + len(values),
                    page_number=span.page_number,
                    section_title=span.label,
                    content=content,
                    token_count=token_count,
                    chunk_metadata=self._metadata(
                        start=cursor,
                        end=content_end,
                        span=span,
                        parser_metadata=parser_metadata,
                        language=language,
                    ),
                )
            )
            if split_at >= span_end:
                break
            next_cursor = _trim_left(
                extracted_text,
                self._overlap_start(extracted_text, span.start, split_at),
                span_end,
            )
            if next_cursor <= cursor or next_cursor >= span_end:
                raise ChunkingError()
            cursor = next_cursor
        return values

    def _hard_end(self, value: str, start: int, end: int) -> int:
        """Find a deterministic character end whose actual token count is bounded."""

        lower = start + 1
        upper = end
        best = start
        while lower <= upper:
            middle = (lower + upper) // 2
            if self.tokenizer.count_tokens(value[start:middle]) <= self.config.maximum_tokens:
                best = middle
                lower = middle + 1
            else:
                upper = middle - 1
        while (
            best > start
            and self.tokenizer.count_tokens(value[start:best]) > self.config.maximum_tokens
        ):
            best -= 1
        if best <= start:
            raise ChunkingError()
        return best

    def _natural_end(self, value: str, start: int, hard_end: int, span_end: int) -> int:
        """Prefer paragraph, sentence, then whitespace endings inside the hard bound."""

        if hard_end >= span_end:
            return span_end
        selected = hard_end
        for match in _NATURAL_BOUNDARY.finditer(value, start, hard_end):
            candidate = match.end()
            if candidate <= start or candidate > hard_end:
                continue
            if self.tokenizer.count_tokens(value[start:candidate]) <= self.config.maximum_tokens:
                selected = candidate
        return selected

    def _overlap_start(self, value: str, span_start: int, end: int) -> int:
        if self.config.overlap_tokens == 0:
            return end
        lower = span_start
        upper = end
        while lower < upper:
            middle = (lower + upper) // 2
            if self.tokenizer.count_tokens(value[middle:end]) <= self.config.overlap_tokens:
                upper = middle
            else:
                lower = middle + 1
        return lower

    def _metadata(
        self,
        *,
        start: int,
        end: int,
        span: TrustedLocationSpan,
        parser_metadata: dict[str, str] | None,
        language: str | None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "char_start": start,
            "char_end": end,
            "locations": [span.as_metadata()],
            "chunking": {
                "version": self.config.configuration_version,
                "embedding_model": self.config.embedding_model,
            },
        }
        if parser_metadata is not None:
            metadata["parser"] = parser_metadata
        if language is not None:
            metadata["language"] = language
        return metadata

    def _validate_candidates(self, candidates: Sequence[ChunkCandidate], text: str) -> None:
        for expected_index, candidate in enumerate(candidates):
            metadata = candidate.chunk_metadata
            start = metadata.get("char_start")
            end = metadata.get("char_end")
            if (
                candidate.chunk_index != expected_index
                or not candidate.content
                or candidate.token_count != self.tokenizer.count_tokens(candidate.content)
                or candidate.token_count <= 0
                or candidate.token_count > self.config.maximum_tokens
                or isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end <= start
                or end > len(text)
                or text[start:end] != candidate.content
            ):
                raise ChunkingError()


def _trusted_spans(text: str, metadata: Mapping[str, object]) -> tuple[TrustedLocationSpan, ...]:
    raw_locations = metadata.get("locations")
    if not isinstance(raw_locations, list) or not raw_locations:
        raise ChunkingError()
    spans: list[TrustedLocationSpan] = []
    previous_end = 0
    for raw_location in raw_locations:
        if not isinstance(raw_location, Mapping):
            raise ChunkingError()
        start = _required_int(raw_location.get("start"))
        end = _required_int(raw_location.get("end"))
        kind = _bounded_string(raw_location.get("kind"), maximum=64)
        label = _optional_string(raw_location.get("label"), maximum=500)
        page_number = _optional_int(raw_location.get("page_number"))
        if (
            start < 0
            or end <= start
            or end > len(text)
            or start < previous_end
            or (page_number is not None and page_number < 1)
        ):
            raise ChunkingError()
        spans.append(
            TrustedLocationSpan(
                start=start,
                end=end,
                kind=kind,
                label=label,
                page_number=page_number,
            )
        )
        previous_end = end
    return tuple(spans)


def _parser_metadata(metadata: Mapping[str, object]) -> dict[str, str] | None:
    parser = metadata.get("parser")
    if not isinstance(parser, Mapping):
        return None
    name = _optional_string(parser.get("name"), maximum=100)
    version = _optional_string(parser.get("version"), maximum=100)
    if name is None or version is None:
        return None
    return {"name": name, "version": version}


def _resolved_language(metadata: Mapping[str, object], fallback: str | None) -> str | None:
    language = metadata.get("language")
    if isinstance(language, Mapping):
        value = _optional_string(language.get("value"), maximum=16)
        if value is not None:
            return value
    return _optional_string(fallback, maximum=16)


def _required_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ChunkingError()
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _required_int(value)


def _bounded_string(value: object, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise ChunkingError()
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ChunkingError()
    return normalized


def _optional_string(value: object, *, maximum: int) -> str | None:
    if value is None:
        return None
    return _bounded_string(value, maximum=maximum)


def _trim_left(value: str, start: int, end: int) -> int:
    while start < end and value[start].isspace():
        start += 1
    return start


def _trim_right(value: str, start: int, end: int) -> int:
    while end > start and value[end - 1].isspace():
        end -= 1
    return end
