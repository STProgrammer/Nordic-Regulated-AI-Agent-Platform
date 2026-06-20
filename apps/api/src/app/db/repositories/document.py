"""Tenant-safe metadata persistence for documents; no object storage behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.document import Document
from app.db.repositories.base import ArchivableTenantScopedRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec, resolve_sort


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

    async def create(self, document: Document) -> Document:
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
