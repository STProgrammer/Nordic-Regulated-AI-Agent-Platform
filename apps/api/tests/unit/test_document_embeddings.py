"""Unit coverage for the bounded, validated embedding provider boundary."""

from __future__ import annotations

import asyncio

import pytest
from app.core.config import AppSettings
from app.db.base import EMBEDDING_DIMENSIONS
from app.services.documents.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingError,
    build_embedding_provider,
    validate_embedding_result,
)


def test_deterministic_provider_is_reproducible_and_fixed_dimension() -> None:
    provider = DeterministicEmbeddingProvider()
    first = asyncio.run(provider.embed(("synthetic alpha", "synthetic beta")))
    second = asyncio.run(provider.embed(("synthetic alpha", "synthetic beta")))

    assert first == second
    assert len(first) == 2
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in first)


@pytest.mark.parametrize(
    "vectors",
    [
        [[0.0] * (EMBEDDING_DIMENSIONS - 1)],
        [[float("nan")] * EMBEDDING_DIMENSIONS],
        [[float("inf")] * EMBEDDING_DIMENSIONS],
    ],
)
def test_embedding_validation_rejects_invalid_dimensions_and_numbers(
    vectors: list[list[float]],
) -> None:
    with pytest.raises(EmbeddingError) as raised:
        validate_embedding_result(vectors, expected_count=1)

    assert raised.value.retryable is False
    assert "nan" not in raised.value.summary.casefold()


def test_deterministic_provider_requires_an_explicit_permitted_environment() -> None:
    assert isinstance(
        build_embedding_provider(
            AppSettings(environment="test", embedding_provider="deterministic")
        ),
        DeterministicEmbeddingProvider,
    )
    with pytest.raises(ValueError):
        AppSettings(environment="production", embedding_provider="deterministic")
