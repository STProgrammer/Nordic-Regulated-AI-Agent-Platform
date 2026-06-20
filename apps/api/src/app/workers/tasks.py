"""Celery tasks whose only business payload is a document UUID."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import Task  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppSettings, get_settings
from app.core.logging import get_logger
from app.db.repositories.document import DocumentRepository
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.documents.chunking import CanonicalTextChunker, ChunkingConfig, TiktokenTokenizer
from app.services.documents.dispatch import CeleryDocumentTaskDispatcher
from app.services.documents.embeddings import (
    EmbeddingError,
    FailingEmbeddingProvider,
    build_embedding_provider,
)
from app.services.documents.indexing import DocumentIndexCoordinator, IndexProcessOutcome
from app.services.documents.parsers.registry import DocumentParserRegistry
from app.services.documents.parsing import DocumentParseCoordinator, ParseProcessOutcome
from app.services.documents.storage import AzureBlobObjectStorage
from app.workers.celery_app import celery_app

_logger = get_logger("workers.document_tasks")
_RECONCILIATION_LIMIT = 100


def _retry_delay(retries: int) -> int:
    """Small finite exponential backoff suitable for local and production-like queues."""

    return min(60, 1 << (retries + 1))


async def _process_document(document_id: UUID, settings: AppSettings) -> ParseProcessOutcome:
    storage = AzureBlobObjectStorage(
        connection_string=settings.object_storage_connection_string_value(),
        container=settings.object_storage_container,
    )
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = DocumentParseCoordinator(
                session,
                storage=storage,
                registry=DocumentParserRegistry(
                    maximum_characters=settings.document_parser_max_extracted_characters,
                    maximum_sections=settings.document_parser_max_sections,
                ),
                maximum_input_bytes=settings.document_parser_max_input_bytes,
                language_minimum_characters=settings.document_language_minimum_characters,
                language_confidence_threshold=settings.document_language_confidence_threshold,
            )
            return await coordinator.process(document_id)
    finally:
        await storage.close()
        # Celery invokes each task through ``asyncio.run``. Dispose the
        # loop-bound asyncpg pool before that event loop closes so the next task
        # never inherits a connection from a previous loop.
        await dispose_database_engines()


async def _mark_exhausted(document_id: UUID, settings: AppSettings) -> None:
    storage = AzureBlobObjectStorage(
        connection_string=settings.object_storage_connection_string_value(),
        container=settings.object_storage_container,
    )
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = DocumentParseCoordinator(
                session,
                storage=storage,
                registry=DocumentParserRegistry(
                    maximum_characters=settings.document_parser_max_extracted_characters,
                    maximum_sections=settings.document_parser_max_sections,
                ),
                maximum_input_bytes=settings.document_parser_max_input_bytes,
                language_minimum_characters=settings.document_language_minimum_characters,
                language_confidence_threshold=settings.document_language_confidence_threshold,
            )
            await coordinator.mark_exhausted_retry(document_id)
    finally:
        await storage.close()
        await dispose_database_engines()


def _index_coordinator(session: AsyncSession, settings: AppSettings) -> DocumentIndexCoordinator:
    """Build short-lived tokenizer/provider adapters only inside a worker task."""

    try:
        provider = build_embedding_provider(settings)
    except EmbeddingError as error:
        # The coordinator still claims the durable row before safely recording a
        # permanent configuration failure; no provider details are persisted.
        provider = FailingEmbeddingProvider(error)
    return DocumentIndexCoordinator(
        session,
        chunker=CanonicalTextChunker(
            tokenizer=TiktokenTokenizer(settings.embedding_tokenizer_encoding),
            config=ChunkingConfig(
                maximum_tokens=settings.document_chunk_max_tokens,
                overlap_tokens=settings.document_chunk_overlap_tokens,
                maximum_chunks=settings.document_chunk_maximum_count,
                configuration_version=settings.embedding_configuration_version,
                embedding_model=settings.embedding_model,
            ),
        ),
        provider=provider,
        embedding_batch_size=settings.embedding_batch_size,
        model_label=settings.embedding_model,
    )


async def _process_index_document(document_id: UUID, settings: AppSettings) -> IndexProcessOutcome:
    coordinator: DocumentIndexCoordinator | None = None
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = _index_coordinator(session, settings)
            return await coordinator.process(document_id)
    finally:
        if coordinator is not None:
            await coordinator.provider.aclose()
        await dispose_database_engines()


async def _mark_index_exhausted(document_id: UUID, settings: AppSettings) -> None:
    coordinator: DocumentIndexCoordinator | None = None
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = _index_coordinator(session, settings)
            await coordinator.mark_exhausted_retry(document_id)
    finally:
        if coordinator is not None:
            await coordinator.provider.aclose()
        await dispose_database_engines()


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.parse_document_task",
    acks_late=True,
    ignore_result=True,
)
def parse_document_task(task: Task, document_id: str) -> str:
    """Parse one UUID-only message with explicit transient retry behavior."""

    try:
        parsed_id = UUID(document_id)
    except ValueError:
        _logger.warning("document.task_invalid_identifier")
        return ParseProcessOutcome.NOOP.value
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_document(parsed_id, settings))
    except Exception as error:
        _logger.warning("document.task_runtime_unavailable", error_type=type(error).__name__)
        outcome = ParseProcessOutcome.TRANSIENT_FAILURE
    if outcome == ParseProcessOutcome.PARSED:
        try:
            # Parsing committed the pending indexing state before this best-effort
            # publication. The reconciler recovers a broker outage safely.
            CeleryDocumentTaskDispatcher().dispatch_index(parsed_id)
        except Exception as error:
            _logger.warning("document.index_dispatch_unavailable", error_type=type(error).__name__)
    if outcome != ParseProcessOutcome.TRANSIENT_FAILURE:
        return outcome.value
    if task.request.retries >= settings.document_parser_task_max_retries:
        try:
            asyncio.run(_mark_exhausted(parsed_id, settings))
        except Exception as error:
            _logger.warning("document.task_exhaustion_unavailable", error_type=type(error).__name__)
        return ParseProcessOutcome.PERMANENT_FAILURE.value
    raise task.retry(countdown=_retry_delay(task.request.retries))


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.index_document_task",
    acks_late=True,
    ignore_result=True,
)
def index_document_task(task: Task, document_id: str) -> str:
    """Index one UUID-only message with explicit bounded retry behavior."""

    try:
        parsed_id = UUID(document_id)
    except ValueError:
        _logger.warning("document.index_task_invalid_identifier")
        return IndexProcessOutcome.NOOP.value
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_index_document(parsed_id, settings))
    except Exception as error:
        _logger.warning("document.index_task_runtime_unavailable", error_type=type(error).__name__)
        outcome = IndexProcessOutcome.TRANSIENT_FAILURE
    if outcome != IndexProcessOutcome.TRANSIENT_FAILURE:
        return outcome.value
    if task.request.retries >= settings.document_indexer_task_max_retries:
        try:
            asyncio.run(_mark_index_exhausted(parsed_id, settings))
        except Exception as error:
            _logger.warning(
                "document.index_task_exhaustion_unavailable", error_type=type(error).__name__
            )
        return IndexProcessOutcome.PERMANENT_FAILURE.value
    raise task.retry(countdown=_retry_delay(task.request.retries))


async def _reconcile(settings: AppSettings) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
    try:
        async with get_sessionmaker(settings)() as session:
            repository = DocumentRepository(session)
            async with session.begin():
                await repository.recover_stale_claims(
                    before=datetime.now(UTC)
                    - timedelta(seconds=settings.document_parser_processing_lease_seconds)
                )
                await repository.recover_stale_index_claims(
                    before=datetime.now(UTC)
                    - timedelta(seconds=settings.document_indexer_processing_lease_seconds)
                )
            parser_candidates = await repository.get_processing_candidates(
                limit=_RECONCILIATION_LIMIT
            )
            index_candidates = await repository.get_indexing_candidates(limit=_RECONCILIATION_LIMIT)
            return (
                tuple(document.id for document in parser_candidates),
                tuple(document.id for document in index_candidates),
            )
    finally:
        await dispose_database_engines()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.workers.tasks.reconcile_document_tasks", ignore_result=True
)
def reconcile_document_tasks() -> int:
    """Resubmit bounded parsing/indexing work after publish failures or stale claims."""

    settings = get_settings()
    try:
        parser_document_ids, index_document_ids = asyncio.run(_reconcile(settings))
        dispatcher = CeleryDocumentTaskDispatcher()
        for document_id in parser_document_ids:
            dispatcher.dispatch_parse(document_id)
        for document_id in index_document_ids:
            dispatcher.dispatch_index(document_id)
        return len(parser_document_ids) + len(index_document_ids)
    except Exception as error:
        _logger.warning("document.reconciliation_unavailable", error_type=type(error).__name__)
        return 0
