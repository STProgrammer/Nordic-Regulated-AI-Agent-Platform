"""Internal document metadata service; upload and parsing are future work."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.repositories.case import CaseRepository
from app.db.repositories.document import DocumentRepository, DocumentUpdateValues
from app.db.repositories.identity import UserRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.common.querying import SortSpec
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class DocumentCreate:
    """Typed metadata persistence input; object storage is not accessed here."""

    organization_id: UUID
    uploaded_by_user_id: UUID
    title: str
    original_filename: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str
    object_storage_key: str
    source_status: str
    confidentiality_level: str
    parsing_status: str
    case_id: UUID | None = None
    language: str | None = None
    page_count: int | None = None


class DocumentService:
    """Compose document metadata writes after scoped relation validation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DocumentRepository(session)
        self.cases = CaseRepository(session)
        self.users = UserRepository(session)

    async def create(self, command: DocumentCreate) -> Document:
        if await self.users.get(command.organization_id, command.uploaded_by_user_id) is None:
            raise NotFoundError("User")
        if (
            command.case_id is not None
            and await self.cases.get(command.organization_id, command.case_id) is None
        ):
            raise NotFoundError("Case")
        document = Document(
            organization_id=command.organization_id,
            uploaded_by_user_id=command.uploaded_by_user_id,
            title=command.title,
            original_filename=command.original_filename,
            file_type=command.file_type,
            mime_type=command.mime_type,
            file_size_bytes=command.file_size_bytes,
            checksum_sha256=command.checksum_sha256,
            object_storage_key=command.object_storage_key,
            source_status=command.source_status,
            confidentiality_level=command.confidentiality_level,
            parsing_status=command.parsing_status,
            case_id=command.case_id,
            language=command.language,
            page_count=command.page_count,
        )
        return await stage_write(
            self.session,
            lambda: self.repository.create(document),
            resource="Document",
        )

    async def get_required(
        self, organization_id: UUID, document_id: UUID, *, include_archived: bool = False
    ) -> Document:
        document = await self.repository.get(
            organization_id, document_id, include_archived=include_archived
        )
        if document is None:
            raise NotFoundError("Document")
        return document

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
        include_archived: bool = False,
    ) -> Page[Document]:
        return await self.repository.list(
            organization_id,
            pagination=pagination,
            sort=sort,
            include_archived=include_archived,
        )

    async def update(
        self, organization_id: UUID, document_id: UUID, values: DocumentUpdateValues
    ) -> Document:
        document = await self.get_required(organization_id, document_id)
        return await stage_write(
            self.session,
            lambda: self.repository.update(document, values),
            resource="Document",
        )

    async def archive(self, organization_id: UUID, document_id: UUID) -> Document:
        archived = await self.repository.archive(organization_id, document_id)
        if archived is None:
            raise NotFoundError("Document")
        await self.session.flush()
        return archived
