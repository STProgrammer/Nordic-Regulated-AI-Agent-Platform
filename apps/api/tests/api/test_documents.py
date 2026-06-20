"""Transport contract tests for the protected Phase 10 document upload endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.api.dependencies import get_authentication_service, get_document_service
from app.core.config import AppSettings
from app.db.models.document import Document
from app.main import create_api_app
from app.services.auth.policy import (
    DocumentAction,
    RetrievalAction,
    authorize_document_action,
    authorize_retrieval_action,
)
from app.services.auth.principal import Principal, RoleName
from app.services.common.pagination import Page, Pagination
from app.services.documents.service import DocumentSourceContext, DocumentUpload
from app.services.errors import ConflictError, InvalidCommandError, NotFoundError
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_document_session_012345678901234567890123456"


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


@dataclass
class _DocumentServiceFake:
    principal: Principal
    case_id: UUID

    def __post_init__(self) -> None:
        self.last_command: DocumentUpload | None = None
        self.document = Document(
            id=uuid4(),
            organization_id=self.principal.organization_id,
            case_id=self.case_id,
            uploaded_by_user_id=self.principal.user_id,
            title="Synthetic attachment",
            original_filename="synthetic.txt",
            file_type="txt",
            mime_type="text/plain",
            file_size_bytes=14,
            checksum_sha256="a" * 64,
            object_storage_key="private/value-that-must-not-leak",
            source_status="draft",
            confidentiality_level="internal",
            parsing_status="pending",
            indexing_status="not_ready",
            indexing_error=None,
            indexed_at=None,
            language=None,
            page_count=None,
            parsing_error=None,
            inserted_at=datetime(2030, 1, 1, tzinfo=UTC),
            updated_at=datetime(2030, 1, 1, tzinfo=UTC),
        )

    async def upload(self, principal: Principal, command: DocumentUpload) -> Document:
        authorize_document_action(principal, DocumentAction.UPLOAD)
        self.last_command = command
        return self.document

    async def get_for_principal(self, principal: Principal, document_id: UUID) -> Document:
        authorize_document_action(principal, DocumentAction.READ)
        if document_id != self.document.id:
            raise NotFoundError("Document")
        return self.document

    async def list_for_case(
        self, principal: Principal, case_id: UUID, *, pagination: Pagination
    ) -> Page[Document]:
        authorize_document_action(principal, DocumentAction.READ)
        if case_id != self.case_id:
            raise NotFoundError("Case")
        return Page(
            items=(self.document,), limit=pagination.limit, offset=pagination.offset, total=1
        )

    async def update_source_status(
        self, principal: Principal, document_id: UUID, *, source_status: str
    ) -> Document:
        authorize_document_action(principal, DocumentAction.UPDATE_SOURCE_STATUS)
        if document_id != self.document.id:
            raise NotFoundError("Document")
        self.document.source_status = source_status
        return self.document

    async def get_source_context(
        self, principal: Principal, document_id: UUID, *, chunk_id: UUID
    ) -> DocumentSourceContext:
        authorize_retrieval_action(principal, RetrievalAction.SEARCH)
        if document_id != self.document.id:
            raise NotFoundError("Document")
        return DocumentSourceContext(
            document_id=self.document.id,
            chunk_id=chunk_id,
            document_title=self.document.title,
            document_file_type=self.document.file_type,
            source_status=self.document.source_status,
            page_number=1,
            section_title="Synthetic section",
            context="Synthetic bounded context",
            truncated=False,
        )

    async def reprocess(self, principal: Principal, document_id: UUID) -> Document:
        authorize_document_action(principal, DocumentAction.REPROCESS)
        if document_id != self.document.id:
            raise NotFoundError("Document")
        if self.document.parsing_status == "processing":
            raise ConflictError("Document parsing")
        self.document.parsing_status = "pending"
        self.document.parsing_error = None
        return self.document

    async def reindex(self, principal: Principal, document_id: UUID) -> Document:
        authorize_document_action(principal, DocumentAction.REINDEX)
        if document_id != self.document.id:
            raise NotFoundError("Document")
        if self.document.parsing_status != "parsed":
            raise InvalidCommandError("The document is not ready for indexing.")
        if self.document.indexing_status in {"pending", "indexing"}:
            raise ConflictError("Document indexing")
        self.document.indexing_status = "pending"
        self.document.indexing_error = None
        return self.document


def _client(*roles: RoleName) -> tuple[TestClient, _DocumentServiceFake]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic Document User",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    documents = _DocumentServiceFake(principal=principal, case_id=uuid4())
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_document_service] = lambda: documents
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, documents


def test_document_upload_uses_multipart_and_returns_safe_metadata_only() -> None:
    client, documents = _client(RoleName.CASE_WORKER)
    with client:
        response = client.post(
            "/api/documents/upload",
            data={
                "case_id": str(documents.case_id),
                "title": "  Synthetic attachment  ",
                "source_status": "draft",
                "confidentiality_level": "internal",
            },
            files={"file": ("synthetic.txt", b"safe test body", "text/plain")},
        )

    assert response.status_code == 201
    assert documents.last_command is not None
    assert documents.last_command.case_id == documents.case_id
    assert documents.last_command.file is not None
    body = response.json()["data"]
    assert body["document_id"] == str(documents.document.id)
    assert body["parsing_status"] == "pending"
    assert "object_storage_key" not in body
    assert "checksum_sha256" not in body
    assert "safe test body" not in response.text


def test_document_upload_requires_a_session_and_upload_role() -> None:
    anonymous, documents = _client(RoleName.CASE_WORKER)
    anonymous.cookies.clear()
    with anonymous:
        unauthenticated = anonymous.post(
            "/api/documents/upload",
            data={"case_id": str(documents.case_id), "email_text": "safe synthetic email"},
        )

    reviewer, reviewer_documents = _client(RoleName.COMPLIANCE_REVIEWER)
    with reviewer:
        forbidden = reviewer.post(
            "/api/documents/upload",
            data={"case_id": str(reviewer_documents.case_id), "email_text": "safe synthetic email"},
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403


def test_document_status_is_metadata_only_and_readable_by_a_reviewer() -> None:
    client, documents = _client(RoleName.COMPLIANCE_REVIEWER)
    documents.document.parsing_status = "failed"
    documents.document.language = "nb"
    documents.document.page_count = 2
    documents.document.parsing_error = "The stored document could not be parsed safely."

    with client:
        response = client.get(f"/api/documents/{documents.document.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["parsing_status"] == "failed"
    assert data["language"] == "nb"
    assert data["page_count"] == 2
    assert "extracted_text" not in data
    assert "object_storage_key" not in data
    assert "checksum_sha256" not in data
    assert "indexing_error" in data
    assert "embedding" not in response.text


def test_document_list_is_case_scoped_and_returns_safe_metadata_only() -> None:
    client, documents = _client(RoleName.READ_ONLY_AUDITOR)
    with client:
        response = client.get(
            "/api/documents",
            params={"case_id": str(documents.case_id), "limit": 1, "offset": 0},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["document_id"] == str(documents.document.id)
    assert "object_storage_key" not in response.text
    assert "checksum_sha256" not in response.text


def test_document_source_status_is_closed_and_governed_by_the_backend() -> None:
    admin, admin_documents = _client(RoleName.ADMIN)
    with admin:
        accepted = admin.patch(
            f"/api/documents/{admin_documents.document.id}/source-status",
            json={"source_status": "deprecated"},
        )
        invalid = admin.patch(
            f"/api/documents/{admin_documents.document.id}/source-status",
            json={"source_status": "approved", "title": "not allowed"},
        )

    worker, worker_documents = _client(RoleName.CASE_WORKER)
    with worker:
        forbidden = worker.patch(
            f"/api/documents/{worker_documents.document.id}/source-status",
            json={"source_status": "approved"},
        )

    assert accepted.status_code == 200
    assert accepted.json()["data"]["source_status"] == "deprecated"
    assert invalid.status_code == 422
    assert forbidden.status_code == 403


def test_source_context_requires_retrieval_access_and_is_bounded_by_the_service() -> None:
    client, documents = _client(RoleName.CASE_WORKER)
    with client:
        accepted = client.get(
            f"/api/documents/{documents.document.id}/context",
            params={"chunk_id": str(uuid4())},
        )

    auditor, auditor_documents = _client(RoleName.READ_ONLY_AUDITOR)
    with auditor:
        forbidden = auditor.get(
            f"/api/documents/{auditor_documents.document.id}/context",
            params={"chunk_id": str(uuid4())},
        )

    assert accepted.status_code == 200
    data = accepted.json()["data"]
    assert data["context"] == "Synthetic bounded context"
    assert data["truncated"] is False
    assert "object_storage_key" not in accepted.text
    assert forbidden.status_code == 403


def test_document_reprocess_is_role_and_state_guarded() -> None:
    client, documents = _client(RoleName.CASE_WORKER)
    documents.document.parsing_status = "parsed"

    with client:
        accepted = client.post(f"/api/documents/{documents.document.id}/reprocess")
    assert accepted.status_code == 202
    assert accepted.json()["data"]["parsing_status"] == "pending"

    documents.document.parsing_status = "processing"
    with client:
        conflict = client.post(f"/api/documents/{documents.document.id}/reprocess")
    assert conflict.status_code == 409

    reviewer, reviewer_documents = _client(RoleName.COMPLIANCE_REVIEWER)
    with reviewer:
        forbidden = reviewer.post(f"/api/documents/{reviewer_documents.document.id}/reprocess")
    assert forbidden.status_code == 403


def test_document_reindex_is_metadata_only_and_role_state_guarded() -> None:
    client, documents = _client(RoleName.MANAGER)
    documents.document.parsing_status = "parsed"
    documents.document.indexing_status = "indexed"

    with client:
        accepted = client.post(f"/api/documents/{documents.document.id}/reindex")
    assert accepted.status_code == 202
    assert accepted.json()["data"]["indexing_status"] == "pending"
    assert "chunk" not in accepted.text

    documents.document.indexing_status = "indexing"
    with client:
        conflict = client.post(f"/api/documents/{documents.document.id}/reindex")
    assert conflict.status_code == 409

    reviewer, reviewer_documents = _client(RoleName.COMPLIANCE_REVIEWER)
    reviewer_documents.document.parsing_status = "parsed"
    reviewer_documents.document.indexing_status = "indexed"
    with reviewer:
        forbidden = reviewer.post(f"/api/documents/{reviewer_documents.document.id}/reindex")
    assert forbidden.status_code == 403
