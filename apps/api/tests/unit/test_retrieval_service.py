from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from app.db.base import EMBEDDING_DIMENSIONS
from app.db.repositories.retrieval import RetrievalRepository
from app.services.audit.service import AuditService
from app.services.auth.principal import Principal, RoleName
from app.services.documents.embeddings import EmbeddingError
from app.services.errors import RetrievalUnavailableError
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.types import PersistenceCandidate, RetrievalMethod, RetrievalRequest


class _Provider:
    def __init__(self, vector: list[float] | None = None, error: Exception | None = None) -> None:
        self.vector = vector if vector is not None else [0.1] * EMBEDDING_DIMENSIONS
        self.error = error
        self.calls = 0
        self.closed = False

    async def embed(self, values: Sequence[str]) -> tuple[list[float], ...]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert len(values) == 1
        return (self.vector,)

    async def aclose(self) -> None:
        self.closed = True


@dataclass
class _Case:
    id: UUID


class _Candidates:
    async def validate_document_selection(
        self, _organization_id: UUID, _document_ids: tuple[UUID, ...]
    ) -> None:
        return None

    async def semantic_candidates(self, **_kwargs: object) -> tuple[PersistenceCandidate, ...]:
        return (_candidate(RetrievalMethod.SEMANTIC, 1),)

    async def keyword_candidates(self, **_kwargs: object) -> tuple[PersistenceCandidate, ...]:
        return (_candidate(RetrievalMethod.KEYWORD, 1),)


def _candidate(method: RetrievalMethod, rank: int) -> PersistenceCandidate:
    return PersistenceCandidate(
        chunk_id=UUID("00000000-0000-0000-0000-000000000010"),
        document_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_title="Synthetic policy",
        document_file_type="txt",
        chunk_index=0,
        page_number=1,
        section_title="Section",
        source_status="deprecated",
        excerpt_content="Synthetic source content that is deliberately bounded.",
        method=method,
        method_rank=rank,
    )


def _service(provider: _Provider, case_id: UUID) -> RetrievalService:
    service = RetrievalService(
        AsyncMock(),
        provider_factory=lambda: provider,
        default_result_limit=10,
        maximum_result_limit=20,
        semantic_candidate_limit=20,
        keyword_candidate_limit=20,
        rank_fusion_constant=60,
        maximum_query_characters=100,
        maximum_document_selections=5,
        maximum_excerpt_characters=20,
    )
    service._cases = type("Cases", (), {"get": AsyncMock(return_value=_Case(case_id))})()
    service._repository = cast(RetrievalRepository, _Candidates())
    service._audit = cast(AuditService, SimpleNamespace(record_event=AsyncMock()))
    return service


def test_service_embeds_once_merges_candidates_closes_provider_and_audits_safely() -> None:
    case_id = uuid4()
    provider = _Provider()
    service = _service(provider, case_id)
    principal = Principal(uuid4(), uuid4(), "Synthetic", "nb", frozenset({RoleName.MANAGER}))

    sources = asyncio.run(
        service.search(
            principal,
            RetrievalRequest(
                case_id=case_id,
                query="synthetic policy",
                result_limit=1,
                source_statuses=("deprecated",),
                document_ids=(),
            ),
        )
    )

    assert provider.calls == 1
    assert provider.closed is True
    assert len(sources) == 1
    assert sources[0].rank == 1
    assert sources[0].excerpt.endswith("…")
    recorded_call = cast(AsyncMock, service._audit.record_event).await_args
    assert recorded_call is not None
    command = recorded_call.args[0]
    assert command.event_data["query_length"] == len("synthetic policy")
    assert "query" not in command.event_data
    assert "chunk_id" not in command.event_data


def test_invalid_provider_output_is_neutral_and_the_provider_is_closed() -> None:
    case_id = uuid4()
    provider = _Provider(vector=[0.1] * (EMBEDDING_DIMENSIONS - 1))
    service = _service(provider, case_id)
    principal = Principal(uuid4(), uuid4(), "Synthetic", "nb", frozenset({RoleName.ADMIN}))

    with pytest.raises(RetrievalUnavailableError):
        asyncio.run(
            service.search(
                principal,
                RetrievalRequest(case_id, "safe", 1, (), ()),
            )
        )
    assert provider.closed is True


def test_provider_errors_are_neutralized() -> None:
    case_id = uuid4()
    provider = _Provider(error=EmbeddingError(retryable=True))
    service = _service(provider, case_id)
    principal = Principal(uuid4(), uuid4(), "Synthetic", "nb", frozenset({RoleName.ADMIN}))

    with pytest.raises(RetrievalUnavailableError):
        asyncio.run(service.search(principal, RetrievalRequest(case_id, "safe", 1, (), ())))
