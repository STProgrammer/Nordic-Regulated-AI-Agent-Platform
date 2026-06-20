"""Parameterized, tenant-governed candidate queries for hybrid retrieval."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.document import Document, DocumentChunk
from app.services.retrieval.types import PersistenceCandidate, RetrievalMethod, RetrievalScope


class RetrievalRepository:
    """Persistence-only access to minimal Phase 12 chunk data.

    Policy resolves the scope before this repository is called, but both
    candidate queries repeat every visibility predicate to make the SQL itself
    the data-leak prevention boundary.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def validate_document_selection(
        self, organization_id: UUID, document_ids: tuple[UUID, ...]
    ) -> None:
        """Require every explicitly selected id to be a visible current-tenant document."""

        if not document_ids:
            return
        statement = select(Document.id).where(
            Document.organization_id == organization_id,
            Document.id.in_(document_ids),
            Document.archived_at.is_(None),
        )
        visible_ids = set((await self.session.scalars(statement)).all())
        if len(visible_ids) != len(document_ids):
            from app.services.errors import NotFoundError

            raise NotFoundError("Document")

    async def semantic_candidates(
        self,
        *,
        query_embedding: list[float],
        scope: RetrievalScope,
        candidate_limit: int,
        excerpt_fetch_characters: int,
    ) -> tuple[PersistenceCandidate, ...]:
        """Search the existing pgvector cosine index with every mandatory predicate."""

        distance = cast(
            ColumnElement[object], DocumentChunk.embedding.cosine_distance(query_embedding)
        )
        rows = await self._candidate_rows(
            scope=scope,
            candidate_limit=candidate_limit,
            excerpt_fetch_characters=excerpt_fetch_characters,
            order_by=cast(
                tuple[ColumnElement[object], ...],
                (
                    distance.asc(),
                    Document.id.asc(),
                    DocumentChunk.chunk_index.asc(),
                    DocumentChunk.id.asc(),
                ),
            ),
        )
        return _to_candidates(rows, method=RetrievalMethod.SEMANTIC)

    async def keyword_candidates(
        self,
        *,
        full_text_query: str,
        scope: RetrievalScope,
        candidate_limit: int,
        excerpt_fetch_characters: int,
    ) -> tuple[PersistenceCandidate, ...]:
        """Search PostgreSQL's simple GIN full-text index through bound values only."""

        tsquery = func.websearch_to_tsquery("simple", full_text_query)
        document_vector = func.to_tsvector("simple", DocumentChunk.content)
        rank = cast(ColumnElement[object], func.ts_rank_cd(document_vector, tsquery))
        rows = await self._candidate_rows(
            scope=scope,
            candidate_limit=candidate_limit,
            excerpt_fetch_characters=excerpt_fetch_characters,
            additional_predicate=cast(ColumnElement[bool], document_vector.op("@@")(tsquery)),
            order_by=cast(
                tuple[ColumnElement[object], ...],
                (
                    rank.desc(),
                    Document.id.asc(),
                    DocumentChunk.chunk_index.asc(),
                    DocumentChunk.id.asc(),
                ),
            ),
        )
        return _to_candidates(rows, method=RetrievalMethod.KEYWORD)

    async def _candidate_rows(
        self,
        *,
        scope: RetrievalScope,
        candidate_limit: int,
        excerpt_fetch_characters: int,
        order_by: tuple[ColumnElement[object], ...],
        additional_predicate: ColumnElement[bool] | None = None,
    ) -> list[RowMapping]:
        """Select no more than the presentation-safe candidate fields needed by fusion."""

        if candidate_limit <= 0 or excerpt_fetch_characters <= 0:
            raise ValueError("retrieval limits must be positive")
        predicates: list[ColumnElement[bool]] = [
            DocumentChunk.organization_id == scope.organization_id,
            Document.organization_id == scope.organization_id,
            Document.archived_at.is_(None),
            Document.parsing_status == "parsed",
            Document.indexing_status == "indexed",
            Document.source_status.in_(scope.source_statuses),
        ]
        if not scope.restricted_entitled:
            predicates.append(Document.confidentiality_level != "restricted")
        if scope.document_ids:
            predicates.append(Document.id.in_(scope.document_ids))
        if additional_predicate is not None:
            predicates.append(additional_predicate)
        statement = (
            select(
                DocumentChunk.id.label("chunk_id"),
                Document.id.label("document_id"),
                Document.title.label("document_title"),
                Document.file_type.label("document_file_type"),
                DocumentChunk.chunk_index.label("chunk_index"),
                DocumentChunk.page_number.label("page_number"),
                DocumentChunk.section_title.label("section_title"),
                Document.source_status.label("source_status"),
                func.left(DocumentChunk.content, excerpt_fetch_characters).label("excerpt_content"),
            )
            .join(
                Document,
                (Document.id == DocumentChunk.document_id)
                & (Document.organization_id == DocumentChunk.organization_id),
            )
            .where(*predicates)
            .order_by(*order_by)
            .limit(candidate_limit)
        )
        return list((await self.session.execute(statement)).mappings().all())


def _to_candidates(
    rows: list[RowMapping], *, method: RetrievalMethod
) -> tuple[PersistenceCandidate, ...]:
    """Attach one-based method-local ranks without returning database score fields."""

    candidates: list[PersistenceCandidate] = []
    for rank, row in enumerate(rows, start=1):
        candidates.append(
            PersistenceCandidate(
                chunk_id=cast(UUID, row["chunk_id"]),
                document_id=cast(UUID, row["document_id"]),
                document_title=cast(str, row["document_title"]),
                document_file_type=cast(str, row["document_file_type"]),
                chunk_index=cast(int, row["chunk_index"]),
                page_number=cast(int | None, row["page_number"]),
                section_title=cast(str | None, row["section_title"]),
                source_status=cast(str, row["source_status"]),
                excerpt_content=cast(str, row["excerpt_content"]),
                method=method,
                method_rank=rank,
            )
        )
    return tuple(candidates)
