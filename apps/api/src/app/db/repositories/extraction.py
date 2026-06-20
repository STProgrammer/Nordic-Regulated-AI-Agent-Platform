"""Tenant-scoped persistence access for source-linked extracted fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import DocumentChunk
from app.db.models.workflow import ExtractedField


@dataclass(frozen=True)
class ExtractedFieldWithDocument:
    field: ExtractedField
    document_id: UUID | None


class ExtractedFieldRepository:
    """Keep all reads tied to organization, case, and selected workflow run."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, field: ExtractedField) -> ExtractedField:
        self.session.add(field)
        return field

    async def list_for_run(
        self, organization_id: UUID, case_id: UUID, workflow_run_id: UUID
    ) -> tuple[ExtractedFieldWithDocument, ...]:
        statement = (
            select(ExtractedField, DocumentChunk.document_id)
            .outerjoin(
                DocumentChunk,
                (DocumentChunk.organization_id == ExtractedField.organization_id)
                & (DocumentChunk.id == ExtractedField.source_chunk_id),
            )
            .where(
                ExtractedField.organization_id == organization_id,
                ExtractedField.case_id == case_id,
                ExtractedField.workflow_run_id == workflow_run_id,
            )
            .order_by(
                ExtractedField.field_name.asc(),
                ExtractedField.inserted_at.asc(),
                ExtractedField.id.asc(),
            )
        )
        return tuple(
            ExtractedFieldWithDocument(field=row[0], document_id=row[1])
            for row in (await self.session.execute(statement)).all()
        )

    async def get_for_update(
        self, organization_id: UUID, case_id: UUID, workflow_run_id: UUID, field_id: UUID
    ) -> ExtractedField | None:
        statement = (
            select(ExtractedField)
            .where(
                ExtractedField.organization_id == organization_id,
                ExtractedField.case_id == case_id,
                ExtractedField.workflow_run_id == workflow_run_id,
                ExtractedField.id == field_id,
            )
            .with_for_update()
        )
        return cast(ExtractedField | None, await self.session.scalar(statement))
