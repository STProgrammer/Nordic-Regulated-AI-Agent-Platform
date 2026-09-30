"""Tenant-safe metadata persistence for documents; no object storage behavior."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.document import Document, DocumentChunk, DocumentText
from app.db.repositories.base import ArchivableTenantScopedRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec, resolve_sort
from app.services.retrieval.types import RetrievalScope


@dataclass(frozen=True)
class DocumentUpdateValues:
    """Explicit document metadata fields; parsing/storage logic arrives later."""

    title: str | None = None
    language: str | None = None
    source_status: str | None = None
    confidentiality_level: str | None = None
    parsing_status: str | None = None
    parsing_error: str | None = None
    page_count: int | None = None


@dataclass(frozen=True)
class DocumentChunkInsert:
    """Validated retrieval data ready for one atomic document-index replacement."""

    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    token_count: int
    chunk_metadata: dict[str, object]
    embedding: list[float]


@dataclass(frozen=True)
class DocumentIndexingInput:
    """Database-derived document identity and canonical text for worker-only indexing."""

    document: Document
    extracted_text: str
    extraction_metadata: dict[str, object]


@dataclass(frozen=True)
class DocumentContextProjection:
    """The only persisted fields permitted to leave the context repository."""

    document_id: UUID
    chunk_id: UUID
    document_title: str
    document_file_type: str
    source_status: str
    page_number: int | None
    section_title: str | None
    context: str


class DocumentRepository(ArchivableTenantScopedRepository[Document]):
    """Metadata-level document access with shared tenant/archive conditions."""

    _sort_columns = {
        "inserted_at": cast(ColumnElement[object], Document.inserted_at),
        "updated_at": cast(ColumnElement[object], Document.updated_at),
        "title": cast(ColumnElement[object], Document.title),
    }

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session,
            Document,
            id_column=cast(ColumnElement[UUID], Document.id),
            organization_column=cast(ColumnElement[UUID], Document.organization_id),
            archived_at_column=cast(ColumnElement[datetime | None], Document.archived_at),
        )

    async def add(self, document: Document) -> Document:
        self.session.add(document)
        return document

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
        include_archived: bool = False,
    ) -> Page[Document]:
        order = resolve_sort(
            sort,
            allowed=self._sort_columns,
            default=SortSpec("inserted_at"),
            tie_breaker=cast(ColumnElement[object], Document.id),
        )
        return await self.list_page(
            organization_id,
            pagination=pagination,
            order_by=order,
            include_archived=include_archived,
        )

    async def list_for_case(
        self,
        organization_id: UUID,
        case_id: UUID,
        *,
        pagination: Pagination,
    ) -> Page[Document]:
        """Return only active documents attached to one active current-tenant case."""

        order = resolve_sort(
            None,
            allowed=self._sort_columns,
            default=SortSpec("inserted_at"),
            tie_breaker=cast(ColumnElement[object], Document.id),
        )
        return await self.list_page(
            organization_id,
            pagination=pagination,
            order_by=order,
            additional=(Document.case_id == case_id,),
        )

    async def update_source_status(
        self, organization_id: UUID, document_id: UUID, *, source_status: str
    ) -> Document | None:
        """Update only the governance label; physical archival remains untouched."""

        statement = (
            update(Document)
            .where(
                Document.organization_id == organization_id,
                Document.id == document_id,
                Document.archived_at.is_(None),
            )
            .values(source_status=source_status)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_source_context(
        self,
        *,
        scope: RetrievalScope,
        document_id: UUID,
        chunk_id: UUID,
        maximum_characters: int,
    ) -> DocumentContextProjection | None:
        """Load one bounded chunk only after the caller resolved retrieval policy.

        Every Phase 13 visibility predicate is repeated in SQL.  A caller can
        neither widen the range nor use a metadata read to bypass source policy.
        """

        if maximum_characters <= 0:
            raise ValueError("maximum context characters must be positive")
        predicates: list[ColumnElement[bool]] = [
            Document.organization_id == scope.organization_id,
            DocumentChunk.organization_id == scope.organization_id,
            Document.id == document_id,
            DocumentChunk.id == chunk_id,
            Document.archived_at.is_(None),
            Document.parsing_status == "parsed",
            Document.indexing_status == "indexed",
            Document.source_status.in_(scope.source_statuses),
        ]
        if not scope.restricted_entitled:
            predicates.append(Document.confidentiality_level != "restricted")
        if scope.document_ids:
            predicates.append(Document.id.in_(scope.document_ids))
        statement = (
            select(
                Document.id.label("document_id"),
                DocumentChunk.id.label("chunk_id"),
                Document.title.label("document_title"),
                Document.file_type.label("document_file_type"),
                Document.source_status.label("source_status"),
                DocumentChunk.page_number.label("page_number"),
                DocumentChunk.section_title.label("section_title"),
                func.left(DocumentChunk.content, maximum_characters + 1).label("context"),
            )
            .join(
                Document,
                (Document.id == DocumentChunk.document_id)
                & (Document.organization_id == DocumentChunk.organization_id),
            )
            .where(*predicates)
        )
        row = (await self.session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return DocumentContextProjection(
            document_id=cast(UUID, row["document_id"]),
            chunk_id=cast(UUID, row["chunk_id"]),
            document_title=cast(str, row["document_title"]),
            document_file_type=cast(str, row["document_file_type"]),
            source_status=cast(str, row["source_status"]),
            page_number=cast(int | None, row["page_number"]),
            section_title=cast(str | None, row["section_title"]),
            context=cast(str, row["context"]),
        )

    async def update(self, document: Document, values: DocumentUpdateValues) -> Document:
        if values.title is not None:
            document.title = values.title
        if values.language is not None:
            document.language = values.language
        if values.source_status is not None:
            document.source_status = values.source_status
        if values.confidentiality_level is not None:
            document.confidentiality_level = values.confidentiality_level
        if values.parsing_status is not None:
            document.parsing_status = values.parsing_status
        if values.parsing_error is not None:
            document.parsing_error = values.parsing_error
        if values.page_count is not None:
            document.page_count = values.page_count
        return document

    async def claim_pending(self, document_id: UUID) -> Document | None:
        """Atomically move one active pending document to ``processing``.

        The task payload deliberately has no organization id. This query derives
        ownership from the document row and protects duplicate Celery deliveries
        using a conditional update rather than a best-effort read/modify/write.
        """

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "pending",
            )
            .values(parsing_status="processing", parsing_error=None)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def complete_parse(
        self,
        document_id: UUID,
        *,
        extracted_text: str,
        extraction_metadata: dict[str, object],
        language: str,
        page_count: int | None,
    ) -> Document | None:
        """Replace canonical text and terminal metadata atomically after a claim."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "processing",
            )
            .values(
                language=language,
                page_count=page_count,
                parsing_status="parsed",
                parsing_error=None,
                indexing_status="pending",
                indexing_error=None,
            )
            .returning(Document)
        )
        document = (await self.session.execute(statement)).scalar_one_or_none()
        if document is None:
            return None
        upsert = insert(DocumentText).values(
            document_id=document_id,
            extracted_text=extracted_text,
            extraction_metadata=extraction_metadata,
        )
        upsert = upsert.on_conflict_do_update(
            index_elements=[DocumentText.document_id],
            set_={
                "extracted_text": upsert.excluded.extracted_text,
                "extraction_metadata": upsert.excluded.extraction_metadata,
            },
        )
        await self.session.execute(upsert)
        return document

    async def fail_parse(self, document_id: UUID, *, parsing_error: str) -> Document | None:
        """Write a terminal safe error without changing an existing text record."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "processing",
            )
            .values(parsing_status="failed", parsing_error=parsing_error)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def return_to_pending(self, document_id: UUID) -> Document | None:
        """Release a transiently failed claim for a bounded queue retry."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "processing",
            )
            .values(parsing_status="pending", parsing_error=None)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def fail_pending(self, document_id: UUID, *, parsing_error: str) -> Document | None:
        """Finish exhausted transient retries from the safe non-active state."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "pending",
            )
            .values(parsing_status="failed", parsing_error=parsing_error)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def request_reprocess(self, organization_id: UUID, document_id: UUID) -> Document | None:
        """Guard an authorized reprocess transition without deleting last-good text."""

        statement = (
            update(Document)
            .where(
                Document.organization_id == organization_id,
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status.in_(("pending", "failed", "parsed")),
            )
            .values(parsing_status="pending", parsing_error=None)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_processing_candidates(self, *, limit: int) -> tuple[Document, ...]:
        """Return bounded pending rows for reconciliation; never loads raw text."""

        statement: Select[tuple[Document]] = (
            select(Document)
            .where(Document.archived_at.is_(None), Document.parsing_status == "pending")
            .order_by(Document.inserted_at, Document.id)
            .limit(limit)
        )
        return tuple((await self.session.scalars(statement)).all())

    async def recover_stale_claims(self, *, before: datetime) -> tuple[UUID, ...]:
        """Release expired processing leases so a killed worker cannot strand a document."""

        statement = (
            update(Document)
            .where(
                Document.archived_at.is_(None),
                Document.parsing_status == "processing",
                Document.updated_at < before,
            )
            .values(parsing_status="pending", parsing_error=None)
            .returning(Document.id)
        )
        return tuple((await self.session.scalars(statement)).all())

    async def claim_pending_index(self, document_id: UUID) -> Document | None:
        """Atomically claim one parsed document for indexing from its UUID-only task."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "parsed",
                Document.indexing_status == "pending",
            )
            .values(indexing_status="indexing", indexing_error=None)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_indexing_input(self, document_id: UUID) -> DocumentIndexingInput | None:
        """Load canonical text only for a worker that already holds an index claim."""

        statement = (
            select(Document, DocumentText)
            .join(DocumentText, DocumentText.document_id == Document.id)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "parsed",
                Document.indexing_status == "indexing",
            )
        )
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        document, text_record = row._tuple()
        return DocumentIndexingInput(
            document=document,
            extracted_text=text_record.extracted_text,
            extraction_metadata=dict(text_record.extraction_metadata),
        )

    async def complete_index(
        self, document_id: UUID, *, chunks: Sequence[DocumentChunkInsert]
    ) -> Document | None:
        """Replace all chunks and finalize one active claim in the current transaction."""

        # This guard takes the document-row lock before deleting existing chunks.
        # A parser completion that makes this index stale must wait and then change
        # the state away from ``indexing`` before a later replacement can proceed.
        guard = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "parsed",
                Document.indexing_status == "indexing",
            )
            .values(indexing_error=None)
            .returning(Document.organization_id)
        )
        organization_id = (await self.session.execute(guard)).scalar_one_or_none()
        if organization_id is None:
            return None
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        if chunks:
            await self.session.execute(
                insert(DocumentChunk),
                [
                    {
                        "organization_id": organization_id,
                        "document_id": document_id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "section_title": chunk.section_title,
                        "content": chunk.content,
                        "token_count": chunk.token_count,
                        "chunk_metadata": chunk.chunk_metadata,
                        "embedding": chunk.embedding,
                    }
                    for chunk in chunks
                ],
            )
        statement = (
            update(Document)
            .where(Document.id == document_id, Document.indexing_status == "indexing")
            .values(
                indexing_status="indexed",
                indexing_error=None,
                indexed_at=datetime.now(UTC),
            )
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def fail_index(self, document_id: UUID, *, indexing_error: str) -> Document | None:
        """Record a neutral permanent index failure without deleting prior chunks."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.indexing_status == "indexing",
            )
            .values(indexing_status="failed", indexing_error=indexing_error)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def return_index_to_pending(self, document_id: UUID) -> Document | None:
        """Release an active index claim after a retryable worker/provider failure."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.indexing_status == "indexing",
            )
            .values(indexing_status="pending", indexing_error=None)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def fail_pending_index(
        self, document_id: UUID, *, indexing_error: str
    ) -> Document | None:
        """Finish exhausted retries only when no active worker still owns the document."""

        statement = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.indexing_status == "pending",
            )
            .values(indexing_status="failed", indexing_error=indexing_error)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def request_reindex(self, organization_id: UUID, document_id: UUID) -> Document | None:
        """Queue one eligible parsed document without disturbing its current chunks."""

        statement = (
            update(Document)
            .where(
                Document.organization_id == organization_id,
                Document.id == document_id,
                Document.archived_at.is_(None),
                Document.parsing_status == "parsed",
                Document.indexing_status.in_(("indexed", "failed")),
            )
            .values(indexing_status="pending", indexing_error=None)
            .returning(Document)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_indexing_candidates(self, *, limit: int) -> tuple[Document, ...]:
        """Return bounded pending index rows for durable post-publish recovery."""

        statement: Select[tuple[Document]] = (
            select(Document)
            .where(
                Document.archived_at.is_(None),
                Document.parsing_status == "parsed",
                Document.indexing_status == "pending",
            )
            .order_by(Document.updated_at, Document.id)
            .limit(limit)
        )
        return tuple((await self.session.scalars(statement)).all())

    async def recover_stale_index_claims(self, *, before: datetime) -> tuple[UUID, ...]:
        """Release expired index claims without inspecting text, vectors, or provider state."""

        statement = (
            update(Document)
            .where(
                Document.archived_at.is_(None),
                Document.indexing_status == "indexing",
                Document.updated_at < before,
            )
            .values(indexing_status="pending", indexing_error=None)
            .returning(Document.id)
        )
        return tuple((await self.session.scalars(statement)).all())
