"""Deliberately small deterministic query normalization for retrieval."""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from app.services.errors import InvalidCommandError
from app.services.retrieval.types import RewrittenQuery

_WHITESPACE = re.compile(r"\s+")


class QueryRewriter(Protocol):
    """Allows later graph-owned planning without widening this Phase 13 contract."""

    def rewrite(self, query: str, *, maximum_characters: int) -> RewrittenQuery:
        """Return exact normalized semantic and safe full-text forms."""


class DeterministicQueryRewriter:
    """Normalize boundaries only; never translate, expand, prompt, or call a model."""

    def rewrite(self, query: str, *, maximum_characters: int) -> RewrittenQuery:
        if maximum_characters <= 0:
            raise ValueError("maximum_characters must be positive")
        normalized = _normalize_query(query)
        if not normalized:
            raise InvalidCommandError("The retrieval query must not be blank.")
        if len(normalized) > maximum_characters:
            raise InvalidCommandError("The retrieval query is too long.")

        # The bounded expansion contract is intentionally identity-only: the
        # normalized user terms are passed unchanged to both methods.  A keyword
        # form is omitted when PostgreSQL would have no lexemes to search.
        return RewrittenQuery(
            semantic_query=normalized,
            full_text_query=normalized
            if any(character.isalnum() for character in normalized)
            else None,
        )


def _normalize_query(query: str) -> str:
    """Collapse Unicode whitespace/control boundaries while retaining language terms."""

    normalized = unicodedata.normalize("NFKC", query)
    boundary_safe = "".join(
        " " if character.isspace() or unicodedata.category(character).startswith("C") else character
        for character in normalized
    )
    return _WHITESPACE.sub(" ", boundary_safe).strip()
