"""PostgreSQL/pgvector/GIN coverage for Phase 13's governed candidate queries."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

from app.core.config import AppSettings
from app.db.base import EMBEDDING_DIMENSIONS
from app.db.models import Document, DocumentChunk
from app.db.repositories.retrieval import RetrievalRepository
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.retrieval.merging import merge_candidates
from app.services.retrieval.types import RetrievalScope


class TenantSeed(Protocol):
    primary_organization_id: UUID
    isolated_organization_id: UUID
    primary_document_id: UUID
    isolated_document_id: UUID


def test_hybrid_candidate_queries_use_current_tenant_indexed_sources_only(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_assert_hybrid_candidates(database_settings, tenant_seed))


async def _assert_hybrid_candidates(settings: AppSettings, seed: TenantSeed) -> None:
    vector = [0.25] * EMBEDDING_DIMENSIONS
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
                        content="Norsk forskrift REF-42 om bankkontroll.",
                        token_count=8,
                        chunk_metadata={},
                        embedding=vector,
                    ),
                    DocumentChunk(
                        organization_id=isolated.organization_id,
                        document_id=isolated.id,
                        chunk_index=0,
                        page_number=1,
                        section_title="Foreign",
                        content="Norsk forskrift REF-42 isolert tenant innhold.",
                        token_count=8,
                        chunk_metadata={},
                        embedding=vector,
                    ),
                )
            )
            await session.commit()

            repository = RetrievalRepository(session)
            scope = RetrievalScope(
                organization_id=seed.primary_organization_id,
                source_statuses=("approved",),
                document_ids=(),
                restricted_entitled=False,
            )
            semantic = await repository.semantic_candidates(
                query_embedding=vector,
                scope=scope,
                candidate_limit=10,
                excerpt_fetch_characters=40,
            )
            keyword = await repository.keyword_candidates(
                full_text_query="forskrift REF-42 bankkontroll",
                scope=scope,
                candidate_limit=10,
                excerpt_fetch_characters=40,
            )
            merged = merge_candidates((*semantic, *keyword), fusion_constant=60)

            assert [candidate.document_id for candidate in semantic] == [primary.id]
            assert [candidate.document_id for candidate in keyword] == [primary.id]
            assert len(merged) == 1
            assert merged[0].retrieval_methods == ("semantic", "keyword")
            assert len(semantic[0].excerpt_content) <= 40
    finally:
        await dispose_database_engines()
