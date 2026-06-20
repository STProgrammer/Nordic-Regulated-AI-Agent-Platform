"""Typed parser results and safe, stable parsing failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SafeParseErrorCode(StrEnum):
    """Non-sensitive terminal outcomes persisted on a document."""

    EMPTY_TEXT = "empty_text"
    INPUT_TOO_LARGE = "input_too_large"
    INTEGRITY_MISMATCH = "integrity_mismatch"
    MALFORMED_DOCUMENT = "malformed_document"
    OBJECT_MISSING = "object_missing"
    SECTION_LIMIT_EXCEEDED = "section_limit_exceeded"
    TEXT_LIMIT_EXCEEDED = "text_limit_exceeded"
    UNSUPPORTED_TYPE = "unsupported_type"


_ERROR_SUMMARIES: dict[SafeParseErrorCode, str] = {
    SafeParseErrorCode.EMPTY_TEXT: "No readable text could be extracted from the document.",
    SafeParseErrorCode.INPUT_TOO_LARGE: "The stored document exceeds the parsing limit.",
    SafeParseErrorCode.INTEGRITY_MISMATCH: (
        "The stored document did not pass integrity verification."
    ),
    SafeParseErrorCode.MALFORMED_DOCUMENT: "The stored document could not be parsed safely.",
    SafeParseErrorCode.OBJECT_MISSING: "The stored document is unavailable for parsing.",
    SafeParseErrorCode.SECTION_LIMIT_EXCEEDED: "The document exceeds the parsing section limit.",
    SafeParseErrorCode.TEXT_LIMIT_EXCEEDED: "The document exceeds the extracted-text limit.",
    SafeParseErrorCode.UNSUPPORTED_TYPE: "The stored document type is not supported for parsing.",
}


class ParseFailure(Exception):
    """A deliberately safe permanent parsing failure, never carrying source details."""

    def __init__(self, code: SafeParseErrorCode) -> None:
        super().__init__(code.value)
        self.code = code

    @property
    def summary(self) -> str:
        return _ERROR_SUMMARIES[self.code]


@dataclass(frozen=True)
class LocationSpan:
    """A zero-based, half-open text range with optional source location labels."""

    start: int
    end: int
    kind: str
    label: str | None = None
    page_number: int | None = None

    def as_metadata(self) -> dict[str, int | str]:
        """Render locator-only metadata; the text itself remains only in DocumentText."""

        value: dict[str, int | str] = {"start": self.start, "end": self.end, "kind": self.kind}
        if self.label is not None:
            value["label"] = self.label
        if self.page_number is not None:
            value["page_number"] = self.page_number
        return value


@dataclass(frozen=True)
class LanguageResult:
    """The limited language vocabulary deliberately supported in this phase."""

    language: str
    confidence: float | None


@dataclass(frozen=True)
class ParsedDocument:
    """Canonical text plus compact source-location context for Phase 12."""

    extracted_text: str
    spans: tuple[LocationSpan, ...]
    page_count: int | None
    parser_name: str
    parser_version: str
