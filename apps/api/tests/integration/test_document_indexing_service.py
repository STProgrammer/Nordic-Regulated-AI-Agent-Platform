"""PostgreSQL-backed Phase 12 indexing lifecycle tests with synthetic text only."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

from app.core.config import AppSettings
from app.db.models import Document, DocumentChunk, DocumentText
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.documents.chunking import CanonicalTextChunker, ChunkingConfig, TiktokenTokenizer
from app.services.documents.embeddings import DeterministicEmbeddingProvider
from app.services.documents.indexing import DocumentIndexCoordinator, IndexProcessOutcome
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TenantSeed(Protocol):
    """The shared seed fields needed to index one document safely."""

    primary_document_id: UUID


def test_indexing_persists_complete_chunks_and_atomically_replaces_a_prior_set(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_index_and_replace(database_settings, tenant_seed))


async def _index_and_replace(settings: AppSettings, seed: TenantSeed) -> None:
    first = "Første syntetiske avsnitt med REF-42."
    second = "Andre syntetiske avsnitt med kontroll."
    text = f"{first}\n\n{second}"
    replacement = "Erstattet syntetisk kontrolltekst med REF-99."
    try:
        async with get_sessionmaker(settings)() as session:
            document = await session.get(Document, seed.primary_document_id)
            assert document is not None
            document.parsing_status = "parsed"
            document.indexing_status = "pending"
            document.language = "nb"
            session.add(
                DocumentText(
                    document_id=document.id,
                    extracted_text=text,
                    extraction_metadata={
                        "parser": {"name": "synthetic", "version": "1"},
                        "language": {"value": "nb"},
                        "locations": [
                            {"start": 0, "end": len(first), "kind": "page", "page_number": 1},
                            {
                                "start": len(first) + 2,
                                "end": len(text),
                                "kind": "page",
                                "page_number": 2,
                            },
                        ],
                    },
                )
            )
            await session.commit()

            first_outcome = await _coordinator(session).process(document.id)
            await session.refresh(document)
            first_chunks = list(
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document.id)
                    .order_by(DocumentChunk.chunk_index)
                )
            )
            assert first_outcome == IndexProcessOutcome.INDEXED
            assert document.indexing_status == "indexed"
            assert document.indexed_at is not None
            assert [chunk.chunk_index for chunk in first_chunks] == list(range(len(first_chunks)))
            assert all(len(chunk.embedding) == 1536 for chunk in first_chunks)
            assert all(chunk.organization_id == document.organization_id for chunk in first_chunks)
            assert all("char_start" in chunk.chunk_metadata for chunk in first_chunks)

            text_record = await session.scalar(
                select(DocumentText).where(DocumentText.document_id == document.id)
            )
            assert text_record is not None
            text_record.extracted_text = replacement
            text_record.extraction_metadata = {
                "locations": [
                    {"start": 0, "end": len(replacement), "kind": "page", "page_number": 1}
                ]
            }
            document.indexing_status = "pending"
            await session.commit()

            second_outcome = await _coordinator(session).process(document.id)
            await session.refresh(document)
            replacement_chunks = list(
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document.id)
                    .order_by(DocumentChunk.chunk_index)
                )
            )
            assert second_outcome == IndexProcessOutcome.INDEXED
            assert document.indexing_status == "indexed"
            assert [chunk.chunk_index for chunk in replacement_chunks] == list(
                range(len(replacement_chunks))
            )
            assert all("REF-99" in chunk.content for chunk in replacement_chunks)
            assert all("REF-42" not in chunk.content for chunk in replacement_chunks)
    finally:
        await dispose_database_engines()


def _coordinator(session: AsyncSession) -> DocumentIndexCoordinator:
    return DocumentIndexCoordinator(
        session,
        chunker=CanonicalTextChunker(
            tokenizer=TiktokenTokenizer("cl100k_base"),
            config=ChunkingConfig(
                maximum_tokens=64,
                overlap_tokens=8,
                maximum_chunks=100,
                configuration_version="synthetic-v1",
                embedding_model="text-embedding-3-small",
            ),
        ),
        provider=DeterministicEmbeddingProvider(),
        embedding_batch_size=8,
        model_label="text-embedding-3-small",
    )
