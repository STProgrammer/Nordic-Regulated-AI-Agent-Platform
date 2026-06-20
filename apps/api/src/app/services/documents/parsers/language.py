"""Deterministic, deliberately narrow language detection."""

from __future__ import annotations

from langdetect import (  # type: ignore[import-not-found]
    DetectorFactory,
    LangDetectException,
    detect_langs,
)

from app.services.documents.parsers.types import LanguageResult


def detect_language(
    text: str, *, minimum_characters: int, confidence_threshold: float
) -> LanguageResult:
    """Recognize only English and Norwegian Bokmål, otherwise report ``unknown``."""

    compact = " ".join(text.split())
    if len(compact) < minimum_characters:
        return LanguageResult(language="unknown", confidence=None)
    try:
        # langdetect otherwise varies with process-local random initialization.
        DetectorFactory.seed = 0
        candidates = detect_langs(compact)
    except LangDetectException:
        return LanguageResult(language="unknown", confidence=None)
    if not candidates:
        return LanguageResult(language="unknown", confidence=None)
    candidate = candidates[0]
    confidence = float(candidate.prob)
    normalized = "nb" if candidate.lang == "no" else candidate.lang
    if normalized not in {"nb", "en"} or confidence < confidence_threshold:
        return LanguageResult(language="unknown", confidence=confidence)
    return LanguageResult(language=normalized, confidence=confidence)
