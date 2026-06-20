"""Narrow, validated embedding-provider boundary for document indexing."""

from __future__ import annotations

import math
from collections.abc import Sequence
from hashlib import sha256
from typing import Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    RateLimitError,
)

from app.core.config import AppSettings
from app.db.base import EMBEDDING_DIMENSIONS

_PERMANENT_SUMMARY = "Document embeddings could not be generated safely."
_TRANSIENT_SUMMARY = "Document embedding is temporarily unavailable."


class EmbeddingError(Exception):
    """Safe provider failure classified for the worker's bounded retry policy."""

    def __init__(self, *, retryable: bool) -> None:
        super().__init__(_TRANSIENT_SUMMARY if retryable else _PERMANENT_SUMMARY)
        self.retryable = retryable

    @property
    def summary(self) -> str:
        return _TRANSIENT_SUMMARY if self.retryable else _PERMANENT_SUMMARY


class EmbeddingProvider(Protocol):
    """Provider boundary that accepts ordered bounded batches only."""

    async def embed(self, values: Sequence[str]) -> tuple[list[float], ...]:
        """Return exactly one ordered, finite 1536-dimensional vector per input."""

    async def aclose(self) -> None:
        """Close private network resources, if any."""


class DeterministicEmbeddingProvider:
    """Non-semantic reproducible vectors for explicitly opted-in local/test plumbing."""

    async def embed(self, values: Sequence[str]) -> tuple[list[float], ...]:
        _validate_input_batch(values)
        return tuple(_deterministic_vector(value) for value in values)

    async def aclose(self) -> None:
        return None


class FailingEmbeddingProvider:
    """Defers configuration failure until a document has been safely claimed."""

    def __init__(self, error: EmbeddingError) -> None:
        self._error = error

    async def embed(self, values: Sequence[str]) -> tuple[list[float], ...]:
        del values
        raise self._error

    async def aclose(self) -> None:
        return None


class OpenAIEmbeddingProvider:
    """Official OpenAI client adapter with a content-free failure boundary."""

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
        self._model = model

    async def embed(self, values: Sequence[str]) -> tuple[list[float], ...]:
        _validate_input_batch(values)
        try:
            response = await self._client.embeddings.create(
                input=list(values), model=self._model, dimensions=EMBEDDING_DIMENSIONS
            )
        except (APITimeoutError, APIConnectionError, RateLimitError) as error:
            raise EmbeddingError(retryable=True) from error
        except APIStatusError as error:
            raise EmbeddingError(retryable=error.status_code >= 500) from error
        except Exception as error:
            raise EmbeddingError(retryable=True) from error
        return validate_embedding_result(
            tuple(list(item.embedding) for item in response.data), expected_count=len(values)
        )

    async def aclose(self) -> None:
        await self._client.close()


class AzureOpenAIEmbeddingProvider:
    """Official Azure OpenAI adapter; ``deployment`` remains a non-secret label only."""

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str,
        timeout_seconds: float,
    ) -> None:
        self._client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self._deployment = deployment

    async def embed(self, values: Sequence[str]) -> tuple[list[float], ...]:
        _validate_input_batch(values)
        try:
            response = await self._client.embeddings.create(
                input=list(values), model=self._deployment, dimensions=EMBEDDING_DIMENSIONS
            )
        except (APITimeoutError, APIConnectionError, RateLimitError) as error:
            raise EmbeddingError(retryable=True) from error
        except APIStatusError as error:
            raise EmbeddingError(retryable=error.status_code >= 500) from error
        except Exception as error:
            raise EmbeddingError(retryable=True) from error
        return validate_embedding_result(
            tuple(list(item.embedding) for item in response.data), expected_count=len(values)
        )

    async def aclose(self) -> None:
        await self._client.close()


def build_embedding_provider(settings: AppSettings) -> EmbeddingProvider:
    """Construct the configured provider only in a worker/request invocation path."""

    if settings.embedding_provider == "deterministic":
        # AppSettings already rejects this outside explicit local/test contexts.
        return DeterministicEmbeddingProvider()
    if settings.embedding_api_key is None:
        raise EmbeddingError(retryable=False)
    api_key = settings.embedding_api_key.get_secret_value()
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=settings.embedding_model,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    if settings.embedding_azure_endpoint is None:
        raise EmbeddingError(retryable=False)
    return AzureOpenAIEmbeddingProvider(
        api_key=api_key,
        endpoint=settings.embedding_azure_endpoint.get_secret_value(),
        deployment=settings.embedding_model,
        api_version=settings.embedding_azure_api_version,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


async def embed_in_batches(
    provider: EmbeddingProvider, values: Sequence[str], *, batch_size: int
) -> tuple[list[float], ...]:
    """Preserve batch and original order while validating every provider response."""

    if batch_size <= 0:
        raise ValueError("embedding batch size must be positive")
    vectors: list[list[float]] = []
    for start in range(0, len(values), batch_size):
        batch = values[start : start + batch_size]
        vectors.extend(await provider.embed(batch))
    return validate_embedding_result(tuple(vectors), expected_count=len(values))


def validate_embedding_result(
    vectors: Sequence[Sequence[float]], *, expected_count: int
) -> tuple[list[float], ...]:
    """Reject count, dimension, NaN, and infinity errors before any database write."""

    if expected_count <= 0 or len(vectors) != expected_count:
        raise EmbeddingError(retryable=False)
    validated: list[list[float]] = []
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError(retryable=False)
        normalized: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EmbeddingError(retryable=False)
            number = float(value)
            if not math.isfinite(number):
                raise EmbeddingError(retryable=False)
            normalized.append(number)
        validated.append(normalized)
    return tuple(validated)


def _validate_input_batch(values: Sequence[str]) -> None:
    if not values or any(not isinstance(value, str) or not value for value in values):
        raise EmbeddingError(retryable=False)


def _deterministic_vector(value: str) -> list[float]:
    """Derive a stable non-semantic 1536-vector without retaining source content."""

    seed = sha256(value.encode("utf-8")).digest()
    vector: list[float] = []
    counter = 0
    while len(vector) < EMBEDDING_DIMENSIONS:
        block = sha256(seed + counter.to_bytes(8, "big")).digest()
        for offset in range(0, len(block), 4):
            if len(vector) == EMBEDDING_DIMENSIONS:
                break
            raw = int.from_bytes(block[offset : offset + 4], "big")
            vector.append((raw / 2_147_483_647.5) - 1.0)
        counter += 1
    return vector
