"""PostgreSQL coverage for Phase 14's case-scoped metadata and bounded context."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID, uuid4

from app.core.config import AppSettings
from app.db.base import EMBEDDING_DIMENSIONS
from app.db.models import AuditEvent, Document, DocumentChunk
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.auth.principal import Principal, RoleName
from app.services.common.pagination import Pagination
from app.services.documents.service import DocumentService
from app.services.errors import NotFoundError
from sqlalchemy import select


class TenantSeed(Protocol):
    primary_organization_id: UUID
    primary_user_id: UUID
    primary_case_id: UUID
    primary_document_id: UUID


class _UnusedStorage:
    """Document status/context tests never call the injected object-storage adapter."""


def test_case_document_page_status_audit_and_context_are_scoped_and_bounded(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_assert_document_evidence_contract(database_settings, tenant_seed))


async def _assert_document_evidence_contract(settings: AppSettings, seed: TenantSeed) -> None:
    try:
        async with get_sessionmaker(settings)() as session:
            document = await session.get(Document, seed.primary_document_id)
            assert document is not None
            document.parsing_status = "parsed"
            document.indexing_status = "indexed"
            document.source_status = "approved"
            document.confidentiality_level = "internal"
            chunk = DocumentChunk(
                organization_id=document.organization_id,
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                section_title="Synthetic section",
                content="Synthetic bounded source context for this indexed document.",
                token_count=8,
                chunk_metadata={},
                embedding=[0.25] * EMBEDDING_DIMENSIONS,
            )
            session.add(chunk)
            await session.commit()

            principal = Principal(
                user_id=seed.primary_user_id,
                organization_id=seed.primary_organization_id,
                display_name="Synthetic administrator",
                preferred_language="nb",
                roles=frozenset({RoleName.ADMIN}),
            )
            service = DocumentService(
                session,
                storage=_UnusedStorage(),  # type: ignore[arg-type]
                maximum_upload_bytes=1024,
                maximum_context_characters=24,
            )

            page = await service.list_for_case(
                principal,
                seed.primary_case_id,
                pagination=Pagination(limit=10),
            )
            assert [item.id for item in page.items] == [document.id]

            archived_at = document.archived_at
            updated = await service.update_source_status(
                principal,
                document.id,
                source_status="deprecated",
            )
            assert updated.source_status == "deprecated"
            assert updated.archived_at == archived_at
            event = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.organization_id == seed.primary_organization_id,
                    AuditEvent.event_type == "document.source_status_updated",
                )
            )
            assert event is not None
            assert event.event_data == {
                "previous_source_status": "approved",
                "source_status": "deprecated",
            }

            context = await service.get_source_context(principal, document.id, chunk_id=chunk.id)
            assert context.context == "Synthetic bounded source"
            assert context.truncated is True
            assert context.chunk_id == chunk.id

            # A random chunk cannot turn the endpoint into a document browser.
            try:
                await service.get_source_context(principal, document.id, chunk_id=uuid4())
            except NotFoundError:
                pass
            else:  # pragma: no cover - assertion branch documents the security invariant
                raise AssertionError("foreign or missing chunk context must remain unavailable")
    finally:
        await dispose_database_engines()
