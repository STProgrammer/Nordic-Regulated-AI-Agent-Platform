"""Worker-only durable document chunking, embedding, and index replacement."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.repositories.document import DocumentChunkInsert, DocumentRepository
from app.services.audit.service import AuditEventInput, AuditService, JSONValue
from app.services.documents.chunking import CanonicalTextChunker, ChunkingError
from app.services.documents.embeddings import EmbeddingError, EmbeddingProvider, embed_in_batches

_logger = get_logger("documents.indexing")
_TRANSIENT_SUMMARY = "Document indexing is temporarily unavailable."


class IndexProcessOutcome(StrEnum):
    """Task-facing result that never carries source text, vectors, or provider data."""

    NOOP = "noop"
    INDEXED = "indexed"
    PERMANENT_FAILURE = "permanent_failure"
    TRANSIENT_FAILURE = "transient_failure"


class DocumentIndexCoordinator:
    """Claim one document, validate all candidates, then atomically replace its index."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        chunker: CanonicalTextChunker,
        provider: EmbeddingProvider,
        embedding_batch_size: int,
        model_label: str,
    ) -> None:
        self.session = session
        self.repository = DocumentRepository(session)
        self.audit = AuditService(session)
        self.chunker = chunker
        self.provider = provider
        self.embedding_batch_size = embedding_batch_size
        self.model_label = model_label

    async def process(self, document_id: UUID) -> IndexProcessOutcome:
        """Perform an idempotent index attempt; Celery handles only transient retries."""

        try:
            async with self.session.begin():
                claimed = await self.repository.claim_pending_index(document_id)
            if claimed is None:
                return IndexProcessOutcome.NOOP
            async with self.session.begin():
                source = await self.repository.get_indexing_input(document_id)
        except SQLAlchemyError as error:
            _logger.warning("document.index_claim_unavailable", error_type=type(error).__name__)
            return IndexProcessOutcome.TRANSIENT_FAILURE

        if source is None:
            failed = await self._record_permanent_failure(document_id, "canonical_text_unavailable")
            return IndexProcessOutcome.PERMANENT_FAILURE if failed else IndexProcessOutcome.NOOP

        try:
            candidates = self.chunker.build(
                extracted_text=source.extracted_text,
                extraction_metadata=source.extraction_metadata,
                language=source.document.language,
            )
            vectors = await embed_in_batches(
                self.provider,
                tuple(candidate.content for candidate in candidates),
                batch_size=self.embedding_batch_size,
            )
            chunks = tuple(
                DocumentChunkInsert(
                    chunk_index=candidate.chunk_index,
                    page_number=candidate.page_number,
                    section_title=candidate.section_title,
                    content=candidate.content,
                    token_count=candidate.token_count,
                    chunk_metadata=candidate.chunk_metadata,
                    embedding=vector,
                )
                for candidate, vector in zip(candidates, vectors, strict=True)
            )
        except ChunkingError:
            await self._record_permanent_failure(document_id, "chunking_invalid")
            return IndexProcessOutcome.PERMANENT_FAILURE
        except EmbeddingError as error:
            if error.retryable:
                await self._return_to_pending(document_id)
                return IndexProcessOutcome.TRANSIENT_FAILURE
            await self._record_permanent_failure(document_id, "embedding_invalid")
            return IndexProcessOutcome.PERMANENT_FAILURE
        except Exception as error:
            _logger.warning("document.index_build_unavailable", error_type=type(error).__name__)
            await self._return_to_pending(document_id)
            return IndexProcessOutcome.TRANSIENT_FAILURE

        try:
            async with self.session.begin():
                completed = await self.repository.complete_index(document_id, chunks=chunks)
                if completed is None:
                    return IndexProcessOutcome.NOOP
                await self._record_terminal_event(
                    completed,
                    event_type="document.indexed",
                    event_data={
                        "transition": "indexed",
                        "chunk_count": len(chunks),
                        "token_count": sum(chunk.token_count for chunk in chunks),
                        "embedding_model": self.model_label,
                    },
                )
            return IndexProcessOutcome.INDEXED
        except SQLAlchemyError as error:
            _logger.warning("document.index_persist_unavailable", error_type=type(error).__name__)
            await self._return_to_pending(document_id)
            return IndexProcessOutcome.TRANSIENT_FAILURE

    async def mark_exhausted_retry(self, document_id: UUID) -> None:
        """Convert a durable pending infrastructure retry into a neutral terminal failure."""

        try:
            async with self.session.begin():
                failed = await self.repository.fail_pending_index(
                    document_id, indexing_error=_TRANSIENT_SUMMARY
                )
                if failed is not None:
                    await self._record_terminal_event(
                        failed,
                        event_type="document.index_failed",
                        event_data={
                            "transition": "failed",
                            "failure_code": "infrastructure_unavailable",
                        },
                    )
        except SQLAlchemyError as error:
            _logger.warning(
                "document.index_retry_exhaustion_persist_unavailable",
                error_type=type(error).__name__,
            )

    async def _record_permanent_failure(self, document_id: UUID, failure_code: str) -> bool:
        try:
            async with self.session.begin():
                failed = await self.repository.fail_index(
                    document_id, indexing_error="Document indexing could not be completed safely."
                )
                if failed is None:
                    return False
                await self._record_terminal_event(
                    failed,
                    event_type="document.index_failed",
                    event_data={"transition": "failed", "failure_code": failure_code},
                )
            return True
        except SQLAlchemyError as error:
            _logger.warning(
                "document.index_failure_persist_unavailable", error_type=type(error).__name__
            )
            return False

    async def _return_to_pending(self, document_id: UUID) -> None:
        try:
            async with self.session.begin():
                await self.repository.return_index_to_pending(document_id)
        except SQLAlchemyError as error:
            _logger.warning(
                "document.index_retry_release_unavailable", error_type=type(error).__name__
            )

    async def _record_terminal_event(
        self,
        document: object,
        *,
        event_type: str,
        event_data: dict[str, JSONValue],
    ) -> None:
        # ``Document`` is intentionally not accepted as arbitrary metadata. The
        # narrow attribute reads below are the sole audit shape for this service.
        from app.db.models.document import Document

        if not isinstance(document, Document):
            raise TypeError("Expected document metadata")
        await self.audit.record_event(
            AuditEventInput(
                organization_id=document.organization_id,
                event_type=event_type,
                resource_type="document",
                resource_id=document.id,
                case_id=document.case_id,
                event_data=event_data,
                include_archived_case=True,
            )
        )
