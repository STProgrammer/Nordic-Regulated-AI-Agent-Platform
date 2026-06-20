"""PostgreSQL-backed persistence and tenant-scope coverage for direct RAG answers."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.core.config import AppSettings
from app.db.base import EMBEDDING_DIMENSIONS
from app.db.models import (
    AgentMessage,
    AuditEvent,
    Document,
    DocumentChunk,
    ModelUsageRecord,
    RetrievedSource,
    WorkflowNodeRun,
    WorkflowRun,
)
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.auth.principal import Principal, RoleName
from app.services.retrieval.answering import RagAnswerService
from app.services.retrieval.generator import (
    RagGenerationRequest,
    RagGenerationResult,
)
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.types import AnswerLanguage, RagAnswerCommand, RagAnswerOutcome
from sqlalchemy import func, select


class TenantSeed(Protocol):
    primary_organization_id: UUID
    isolated_organization_id: UUID
    primary_user_id: UUID
    primary_case_id: UUID
    primary_document_id: UUID
    isolated_document_id: UUID


class _EmbeddingProvider:
    async def embed(self, values: Sequence[str]) -> tuple[list[float], ...]:
        return tuple([0.25] * EMBEDDING_DIMENSIONS for _ in values)

    async def aclose(self) -> None:
        return None


class _Generator:
    async def generate(self, request: RagGenerationRequest) -> RagGenerationResult:
        assert request.evidence
        return RagGenerationResult(
            answer="Det syntetiske kravet gjelder kontroll. [S1]",
            refused=False,
            language=request.language,
            provider="test",
            model_name="test-model",
            token_input=10,
            token_output=5,
            latency_ms=2,
        )

    async def aclose(self) -> None:
        return None


def test_direct_rag_answer_persists_only_primary_approved_evidence(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_assert_direct_rag_answer(database_settings, tenant_seed))


async def _assert_direct_rag_answer(settings: AppSettings, seed: TenantSeed) -> None:
    try:
        async with get_sessionmaker(settings)() as session:
            primary = await session.get(Document, seed.primary_document_id)
            isolated = await session.get(Document, seed.isolated_document_id)
            assert primary is not None
            assert isolated is not None
            for document in (primary, isolated):
                document.parsing_status = "parsed"
                document.indexing_status = "indexed"
                document.source_status = "approved"
                document.confidentiality_level = "internal"
            session.add_all(
                (
                    DocumentChunk(
                        organization_id=primary.organization_id,
                        document_id=primary.id,
                        chunk_index=0,
                        page_number=1,
                        section_title="Kontroll",
                        content="Syntetisk kontrollkrav gjelder godkjent bevismateriale.",
                        token_count=8,
                        chunk_metadata={},
                        embedding=[0.25] * EMBEDDING_DIMENSIONS,
                    ),
                    DocumentChunk(
                        organization_id=isolated.organization_id,
                        document_id=isolated.id,
                        chunk_index=0,
                        page_number=1,
                        section_title="Foreign",
                        content="Dette må aldri kunne bli primærtenantens RAG-kilde.",
                        token_count=8,
                        chunk_metadata={},
                        embedding=[0.25] * EMBEDDING_DIMENSIONS,
                    ),
                )
            )
            await session.commit()

            principal = Principal(
                user_id=seed.primary_user_id,
                organization_id=seed.primary_organization_id,
                display_name="Synthetic administrator",
                preferred_language="nb",
                roles=frozenset({RoleName.ADMIN}),
            )
            retrieval = RetrievalService(
                session,
                provider_factory=lambda: _EmbeddingProvider(),
                default_result_limit=3,
                maximum_result_limit=3,
                semantic_candidate_limit=5,
                keyword_candidate_limit=5,
                rank_fusion_constant=60,
                maximum_query_characters=200,
                maximum_document_selections=5,
                maximum_excerpt_characters=200,
            )
            service = RagAnswerService(
                session,
                retrieval=retrieval,
                generator_factory=_Generator,
                maximum_answer_characters=500,
                maximum_evidence_sources=3,
                maximum_evidence_characters=500,
                minimum_evidence_sources=1,
                minimum_evidence_characters=10,
                input_price_per_million=None,
                output_price_per_million=None,
            )

            result = await service.answer(
                principal,
                RagAnswerCommand(
                    case_id=seed.primary_case_id,
                    question="Hvilket kontrollkrav gjelder?",
                    answer_language=AnswerLanguage.NB,
                ),
            )

            assert result.outcome is RagAnswerOutcome.ANSWERED
            assert [citation.label for citation in result.citations] == ["S1"]
            run = await session.get(WorkflowRun, result.run_id)
            assert run is not None
            assert run.status == "completed"
            assert run.workflow_name == "rag_answer"
            assert run.state_snapshot["target_language"] == "nb"
            sources = list(
                (
                    await session.scalars(
                        select(RetrievedSource).where(
                            RetrievedSource.workflow_run_id == result.run_id
                        )
                    )
                ).all()
            )
            assert [source.document_id for source in sources] == [seed.primary_document_id]
            assert [source.citation_label for source in sources] == ["S1"]
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AgentMessage)
                    .where(AgentMessage.workflow_run_id == result.run_id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ModelUsageRecord)
                    .where(ModelUsageRecord.workflow_run_id == result.run_id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(WorkflowNodeRun)
                    .where(WorkflowNodeRun.workflow_run_id == result.run_id)
                )
                == 0
            )
            audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.organization_id == seed.primary_organization_id,
                    AuditEvent.event_type == "rag.answer_completed",
                    AuditEvent.resource_id == result.run_id,
                )
            )
            assert audit is not None
            assert audit.event_data["outcome"] == "answered"
            assert all(
                key not in audit.event_data
                for key in {"query", "excerpt", "chunk_id", "score", "token", "cost"}
            )
    finally:
        await dispose_database_engines()
