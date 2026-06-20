from __future__ import annotations

import pytest
from app.services.errors import InvalidCommandError
from app.services.retrieval.rewriting import DeterministicQueryRewriter


def test_rewriter_normalizes_unicode_boundaries_without_translating_terms() -> None:
    rewritten = DeterministicQueryRewriter().rewrite(
        "  Forskrift\u200b om\n  bank  policy  ", maximum_characters=100
    )

    assert rewritten.semantic_query == "Forskrift om bank policy"
    assert rewritten.full_text_query == "Forskrift om bank policy"


def test_rewriter_omits_keyword_query_without_lexemes_and_rejects_blank_input() -> None:
    rewriter = DeterministicQueryRewriter()

    assert rewriter.rewrite("!!!", maximum_characters=10).full_text_query is None
    with pytest.raises(InvalidCommandError):
        rewriter.rewrite(" \u200b\n", maximum_characters=10)
    with pytest.raises(InvalidCommandError):
        rewriter.rewrite("x" * 11, maximum_characters=10)
