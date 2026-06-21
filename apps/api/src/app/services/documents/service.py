"""Secure document-ingestion coordination without parsing or retrieval behavior."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.document import Document
from app.db.repositories.case import CaseRepository
from app.db.repositories.document import (
    DocumentContextProjection,
    DocumentRepository,
    DocumentUpdateValues,
)
from app.services.audit.service import AuditEventCreate, AuditService, JSONValue
from app.services.auth.policy import (
    CaseAction,
    DocumentAction,
    RetrievalAction,
    authorize_case_action,
    authorize_document_action,
    authorize_retrieval_action,
)
from app.services.auth.principal import Principal
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.common.querying import SortSpec
from app.services.documents.dispatch import DocumentTaskDispatcher
from app.services.documents.keys import document_storage_key
from app.services.documents.storage import ObjectStorage
from app.services.documents.validator import (
    UploadFileLike,
    ValidatedDocument,
    validate_email_text,
    validate_upload_file,
)
from app.services.errors import (
    ConflictError,
    InvalidCommandError,
    NotFoundError,
    QueueUnavailableError,
    StorageUnavailableError,
)
from app.services.retrieval.policy import resolve_source_scope

_logger = get_logger("documents.service")
_SOURCE_STATUSES = frozenset({"approved", "draft", "deprecated", "restricted", "archived"})
_CONFIDENTIALITY_LEVELS = frozenset({"public", "internal", "confidential", "restricted"})


@dataclass(frozen=True)
class DocumentUpload:
    """Caller-controlled upload fields; ownership and storage identity stay server-owned."""

    case_id: UUID
    file: UploadFileLike | None = None
    email_text: str | None = None
    title: str | None = None
    source_status: str = "draft"
    confidentiality_level: str = "internal"


@dataclass(frozen=True)
class DocumentSourceContext:
    """Presentation-safe text window for one explicitly opened evidence source."""

    document_id: UUID
    chunk_id: UUID
    document_title: str
    document_file_type: str
    source_status: str
    page_number: int | None
    section_title: str | None
    context: str
    truncated: bool


class DocumentService:
    """Secure document ingestion, status, and controlled parsing reprocessing."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: ObjectStorage,
        maximum_upload_bytes: int,
        dispatcher: DocumentTaskDispatcher | None = None,
        maximum_context_characters: int = 1_200,
    ) -> None:
        self.session = session
        self.repository = DocumentRepository(session)
        self.cases = CaseRepository(session)
        self.audit = AuditService(session)
        self.storage = storage
        self.maximum_upload_bytes = maximum_upload_bytes
        self.dispatcher = dispatcher
        self.maximum_context_characters = maximum_context_characters

    async def upload(self, principal: Principal, command: DocumentUpload) -> Document:
        """Store a fully validated raw document and atomically stage metadata/audit rows."""

        authorize_document_action(principal, DocumentAction.UPLOAD)
        case = await self.cases.get(principal.organization_id, command.case_id)
        if case is None:
            raise NotFoundError("Case")
        source_status = _validated_source_status(command.source_status)
        confidentiality_level = _validated_confidentiality_level(command.confidentiality_level)
        validated = await self._validated_payload(command)
        title = _normalized_title(command.title, fallback_filename=validated.original_filename)

        document_id = uuid4()
        storage_key = document_storage_key(
            organization_id=principal.organization_id,
            case_id=case.id,
            document_id=document_id,
        )
        try:
            await self.storage.put_bytes(
                key=storage_key,
                payload=validated.payload,
                content_type=validated.mime_type,
            )
        except Exception as error:
            _logger.warning("document.storage_write_failed", error_type=type(error).__name__)
            raise StorageUnavailableError() from error

        document = Document(
            id=document_id,
            organization_id=principal.organization_id,
            case_id=case.id,
            uploaded_by_user_id=principal.user_id,
            title=title,
            original_filename=validated.original_filename,
            file_type=validated.file_type,
            mime_type=validated.mime_type,
            file_size_bytes=validated.byte_size,
            checksum_sha256=validated.checksum_sha256,
            object_storage_key=storage_key,
            source_status=source_status,
            confidentiality_level=confidentiality_level,
            parsing_status="pending",
            indexing_status="not_ready",
        )
        try:
            created = await stage_write(
                self.session,
                lambda: self.repository.create(document),
                resource="Document",
            )
            await self._record_uploaded_event(created, principal)
            # The request session normally commits in its dependency finalizer.
            # Parsing is different: dispatch must follow a durable upload so the
            # worker never races a transaction it cannot yet observe.
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self._compensate_storage(storage_key)
            raise
        self._dispatch_after_upload(created.id)
        return created

    async def get_for_principal(self, principal: Principal, document_id: UUID) -> Document:
        """Return tenant-scoped metadata only after the reusable document-read policy."""

        authorize_document_action(principal, DocumentAction.READ)
        return await self.get_required(principal.organization_id, document_id)

    async def list_for_case(
        self, principal: Principal, case_id: UUID, *, pagination: Pagination
    ) -> Page[Document]:
        """List safe metadata for one active readable case, never an organization directory."""

        authorize_case_action(principal, CaseAction.READ)
        authorize_document_action(principal, DocumentAction.READ)
        case = await self.cases.get(principal.organization_id, case_id)
        if case is None:
            raise NotFoundError("Case")
        return await self.repository.list_for_case(
            principal.organization_id,
            case.id,
            pagination=pagination,
        )

    async def update_source_status(
        self, principal: Principal, document_id: UUID, *, source_status: str
    ) -> Document:
        """Persist an auditable governance-label change without touching lifecycle state.

        Repeating the existing value is intentionally idempotent: it returns the
        metadata unchanged and emits no second audit event.
        """

        authorize_document_action(principal, DocumentAction.UPDATE_SOURCE_STATUS)
        next_status = _validated_source_status(source_status)
        current = await self.repository.get(principal.organization_id, document_id)
        if current is None:
            raise NotFoundError("Document")
        if current.source_status == next_status:
            return current
        previous_source_status = current.source_status
        updated = await self.repository.update_source_status(
            principal.organization_id,
            document_id,
            source_status=next_status,
        )
        if updated is None:
            raise NotFoundError("Document")
        await self.audit.record_event(
            AuditEventCreate(
                organization_id=updated.organization_id,
                actor_user_id=principal.user_id,
                event_type="document.source_status_updated",
                resource_type="document",
                resource_id=updated.id,
                case_id=updated.case_id,
                event_data={
                    "previous_source_status": previous_source_status,
                    "source_status": updated.source_status,
                },
            )
        )
        await self.session.commit()
        return updated

    async def get_source_context(
        self, principal: Principal, document_id: UUID, *, chunk_id: UUID
    ) -> DocumentSourceContext:
        """Return one bounded permitted chunk window under the Phase 13 policy.

        Metadata reads intentionally allow auditors, while source context does
        not.  The retrieval policy is checked before the content projection.
        """

        authorize_case_action(principal, CaseAction.READ)
        authorize_retrieval_action(principal, RetrievalAction.SEARCH)
        document = await self.repository.get(principal.organization_id, document_id)
        if document is None or document.case_id is None:
            raise NotFoundError("Document")
        case = await self.cases.get(principal.organization_id, document.case_id)
        if case is None:
            raise NotFoundError("Document")
        scope = resolve_source_scope(
            principal,
            requested_statuses=(document.source_status,),
            document_ids=(document.id,),
        )
        projection = await self.repository.get_source_context(
            scope=scope,
            document_id=document.id,
            chunk_id=chunk_id,
            maximum_characters=self.maximum_context_characters,
        )
        if projection is None:
            raise NotFoundError("Document")
        return _source_context_from_projection(
            projection,
            maximum_characters=self.maximum_context_characters,
        )

    async def reprocess(self, principal: Principal, document_id: UUID) -> Document:
        """Safely request a new asynchronous parse without deleting last-good text."""

        authorize_document_action(principal, DocumentAction.REPROCESS)
        current = await self.repository.get(principal.organization_id, document_id)
        if current is None:
            raise NotFoundError("Document")
        if current.parsing_status == "processing":
            raise ConflictError("Document parsing")
        updated = await self.repository.request_reprocess(principal.organization_id, document_id)
        if updated is None:
            # A concurrent worker can only make this state active after a valid
            # dispatch; do not disclose more state than the normal conflict contract.
            raise ConflictError("Document parsing")
        await self.audit.record_event(
            AuditEventCreate(
                organization_id=updated.organization_id,
                actor_user_id=principal.user_id,
                event_type="document.reprocess_requested",
                resource_type="document",
                resource_id=updated.id,
                case_id=updated.case_id,
                event_data={
                    "file_type": updated.file_type,
                    "transition": "pending",
                },
            )
        )
        await self.session.commit()
        if self.dispatcher is not None:
            try:
                self.dispatcher.dispatch_parse(updated.id)
            except Exception as error:
                _logger.warning(
                    "document.reprocess_dispatch_failed", error_type=type(error).__name__
                )
                # The pending state remains durable and reconciliation will pick it
                # up; the client receives a safe operational signal.
                raise QueueUnavailableError() from error
        return updated

    async def reindex(self, principal: Principal, document_id: UUID) -> Document:
        """Request a metadata-only asynchronous index replacement for parsed text."""

        authorize_document_action(principal, DocumentAction.REINDEX)
        current = await self.repository.get(principal.organization_id, document_id)
        if current is None:
            raise NotFoundError("Document")
        if current.parsing_status != "parsed":
            raise InvalidCommandError("The document is not ready for indexing.")
        if current.indexing_status in {"pending", "indexing"}:
            raise ConflictError("Document indexing")
        updated = await self.repository.request_reindex(principal.organization_id, document_id)
        if updated is None:
            raise ConflictError("Document indexing")
        await self.audit.record_event(
            AuditEventCreate(
                organization_id=updated.organization_id,
                actor_user_id=principal.user_id,
                event_type="document.reindex_requested",
                resource_type="document",
                resource_id=updated.id,
                case_id=updated.case_id,
                event_data={
                    "transition": "pending",
                    "embedding_configuration": "current",
                },
            )
        )
        await self.session.commit()
        if self.dispatcher is not None:
            try:
                self.dispatcher.dispatch_index(updated.id)
            except Exception as error:
                _logger.warning("document.reindex_dispatch_failed", error_type=type(error).__name__)
                # The state is already durable; the periodic reconciler will
                # enqueue this UUID without exposing broker implementation data.
                raise QueueUnavailableError() from error
        return updated

    async def get_required(
        self, organization_id: UUID, document_id: UUID, *, include_archived: bool = False
    ) -> Document:
        """Load metadata for future owning document operations only."""

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
        """Retain internal metadata query support without introducing a document list API."""

        return await self.repository.list(
            organization_id,
            pagination=pagination,
            sort=sort,
            include_archived=include_archived,
        )

    async def update(
        self, organization_id: UUID, document_id: UUID, values: DocumentUpdateValues
    ) -> Document:
        """Internal future metadata support; public mutations are deliberately absent."""

        document = await self.get_required(organization_id, document_id)
        return await stage_write(
            self.session,
            lambda: self.repository.update(document, values),
            resource="Document",
        )

    async def archive(self, organization_id: UUID, document_id: UUID) -> Document:
        """Internal future archival support; no public endpoint is introduced here."""

        archived = await self.repository.archive(organization_id, document_id)
        if archived is None:
            raise NotFoundError("Document")
        await self.session.flush()
        return archived

    async def _validated_payload(self, command: DocumentUpload) -> ValidatedDocument:
        if (command.file is None) == (command.email_text is None):
            raise InvalidCommandError("Provide exactly one document payload.")
        if command.file is not None:
            return await validate_upload_file(
                command.file,
                maximum_bytes=self.maximum_upload_bytes,
            )
        if command.email_text is None:
            raise InvalidCommandError("The document command is invalid.")
        return validate_email_text(command.email_text, maximum_bytes=self.maximum_upload_bytes)

    async def _record_uploaded_event(self, document: Document, principal: Principal) -> None:
        event_data: dict[str, JSONValue] = {
            "file_type": document.file_type,
            "file_size_bytes": document.file_size_bytes,
            "source_status": document.source_status,
            "confidentiality_level": document.confidentiality_level,
            "parsing_status": document.parsing_status,
        }
        await self.audit.record_event(
            AuditEventCreate(
                organization_id=document.organization_id,
                actor_user_id=principal.user_id,
                event_type="document.uploaded",
                resource_type="document",
                resource_id=document.id,
                case_id=document.case_id,
                event_data=event_data,
            )
        )

    async def _compensate_storage(self, storage_key: str) -> None:
        try:
            await self.storage.delete(key=storage_key)
        except Exception as error:
            _logger.error("document.storage_compensation_failed", error_type=type(error).__name__)

    def _dispatch_after_upload(self, document_id: UUID) -> None:
        """Best-effort immediate scheduling; reconciliation owns durable recovery."""

        if self.dispatcher is None:
            return
        try:
            self.dispatcher.dispatch_parse(document_id)
        except Exception as error:
            _logger.warning("document.upload_dispatch_failed", error_type=type(error).__name__)


def _validated_source_status(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in _SOURCE_STATUSES:
        raise InvalidCommandError("The source status is invalid.")
    return normalized


def _validated_confidentiality_level(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in _CONFIDENTIALITY_LEVELS:
        raise InvalidCommandError("The confidentiality level is invalid.")
    return normalized


def _normalized_title(value: str | None, *, fallback_filename: str) -> str:
    candidate = fallback_filename.rsplit(".", maxsplit=1)[0] if value is None else value
    normalized = " ".join(candidate.split())
    if not normalized or len(normalized) > 500:
        raise InvalidCommandError("The document title is invalid.")
    return normalized


def _source_context_from_projection(
    projection: DocumentContextProjection, *, maximum_characters: int
) -> DocumentSourceContext:
    """Apply the final hard truncation without exposing locations or raw records."""

    truncated = len(projection.context) > maximum_characters
    return DocumentSourceContext(
        document_id=projection.document_id,
        chunk_id=projection.chunk_id,
        document_title=projection.document_title,
        document_file_type=projection.document_file_type,
        source_status=projection.source_status,
        page_number=projection.page_number,
        section_title=projection.section_title,
        context=projection.context[:maximum_characters],
        truncated=truncated,
    )
