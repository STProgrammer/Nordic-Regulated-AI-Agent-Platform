"""Protected document ingestion, parsing metadata, and reprocessing operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status

from app.api.dependencies import CurrentPrincipalDependency, DocumentServiceDependency
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.api.schemas.documents import (
    DocumentConfidentialityLevel,
    DocumentData,
    DocumentIndexingStatus,
    DocumentListData,
    DocumentParsingStatus,
    DocumentSourceContextData,
    DocumentSourceStatus,
    DocumentSourceStatusUpdateRequest,
)
from app.db.models.document import Document
from app.services.common.pagination import Pagination
from app.services.documents.service import DocumentSourceContext, DocumentUpload

PREFIX = "/documents"
TAG = "Documents"
DESCRIPTION = (
    "Protected document metadata and governance operations. Raw storage, full extracted text, "
    "generic chunks, embeddings, downloads, previews, answers, and citations are not exposed."
)

router = APIRouter()

_DOCUMENT_ERROR_RESPONSES = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "The current role is not allowed."},
    404: {
        "model": ErrorResponse,
        "description": "The requested case, document, or context is unavailable.",
    },
    409: {"model": ErrorResponse, "description": "Document parsing is already active."},
    422: {"model": ErrorResponse, "description": "The document is not ready for indexing."},
    413: {"model": ErrorResponse, "description": "The document exceeds the configured size limit."},
    415: {"model": ErrorResponse, "description": "The document type is not supported."},
    503: {"model": ErrorResponse, "description": "Document storage or queue is unavailable."},
}


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[DocumentData],
    responses=_DOCUMENT_ERROR_RESPONSES,
    summary="Upload one validated document to private storage",
    description=(
        "Accept exactly one of `file` or `email_text` in multipart form data. The API validates "
        "the payload, stores accepted raw bytes privately, and returns metadata only. It does not "
        "parse synchronously, display, download, or retrieve document content."
    ),
)
async def upload_document(
    request: Request,
    principal: CurrentPrincipalDependency,
    documents: DocumentServiceDependency,
    case_id: Annotated[UUID, Form(description="Active case id in the current organization.")],
    file: Annotated[
        UploadFile | None,
        File(description="One supported binary document; mutually exclusive with email_text."),
    ] = None,
    email_text: Annotated[
        str | None,
        Form(description="Pasted email content; mutually exclusive with file."),
    ] = None,
    title: Annotated[str | None, Form(max_length=500)] = None,
    source_status: Annotated[DocumentSourceStatus, Form()] = DocumentSourceStatus.DRAFT,
    confidentiality_level: Annotated[
        DocumentConfidentialityLevel, Form()
    ] = DocumentConfidentialityLevel.INTERNAL,
) -> SuccessResponse[DocumentData]:
    """Keep multipart transport and resource cleanup thin around the document service."""

    try:
        document = await documents.upload(
            principal,
            DocumentUpload(
                case_id=case_id,
                file=file,
                email_text=email_text,
                title=title,
                source_status=source_status.value,
                confidentiality_level=confidentiality_level.value,
            ),
        )
    finally:
        if file is not None:
            await file.close()
    return SuccessResponse(data=_document_data(document), meta=_meta(request))


@router.get(
    "",
    response_model=SuccessResponse[DocumentListData],
    responses=_DOCUMENT_ERROR_RESPONSES,
    summary="List safe document metadata for one readable active case",
    description=(
        "Returns a bounded, stable page of metadata only for the supplied case in the current "
        "organization. It is not an organization-wide document directory and returns no content, "
        "storage data, chunks, checksums, or download links."
    ),
)
async def list_documents(
    request: Request,
    principal: CurrentPrincipalDependency,
    documents: DocumentServiceDependency,
    case_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[DocumentListData]:
    """Keep the case scope explicit and delegate policy/pagination to the service."""

    page = await documents.list_for_case(
        principal,
        case_id,
        pagination=Pagination(limit=limit, offset=offset),
    )
    return SuccessResponse(
        data=DocumentListData(
            items=tuple(_document_data(document) for document in page.items),
            limit=page.limit,
            offset=page.offset,
            total=page.total,
            has_more=page.has_more,
        ),
        meta=_meta(request),
    )


@router.get(
    "/{document_id}",
    response_model=SuccessResponse[DocumentData],
    responses=_DOCUMENT_ERROR_RESPONSES,
    summary="Get safe document parsing metadata",
    description=(
        "Returns metadata only; extracted text, locations, checksums, and storage details are "
        "excluded."
    ),
)
async def get_document(
    document_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    documents: DocumentServiceDependency,
) -> SuccessResponse[DocumentData]:
    """Expose tenant-safe parsing status without adding raw-document access."""

    document = await documents.get_for_principal(principal, document_id)
    return SuccessResponse(data=_document_data(document), meta=_meta(request))


@router.patch(
    "/{document_id}/source-status",
    response_model=SuccessResponse[DocumentData],
    responses=_DOCUMENT_ERROR_RESPONSES,
    summary="Change one document source-governance label",
    description=(
        "Accepts only a closed source-status value. This changes retrieval governance only: it "
        "does not archive or delete the document, change confidentiality, reprocess, re-index, "
        "or expose document content."
    ),
)
async def update_document_source_status(
    document_id: UUID,
    payload: DocumentSourceStatusUpdateRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    documents: DocumentServiceDependency,
) -> SuccessResponse[DocumentData]:
    """Apply the narrow audited governance operation without a generic PATCH surface."""

    document = await documents.update_source_status(
        principal,
        document_id,
        source_status=payload.source_status.value,
    )
    return SuccessResponse(data=_document_data(document), meta=_meta(request))


@router.get(
    "/{document_id}/context",
    response_model=SuccessResponse[DocumentSourceContextData],
    responses=_DOCUMENT_ERROR_RESPONSES,
    summary="Open one bounded, authorized source-context window",
    description=(
        "Returns a fixed server-bounded text window for one selected chunk only after the same "
        "retrieval role, source-status, confidentiality, tenant, and lifecycle checks as governed "
        "retrieval. It never returns a raw document, full text, generic chunk list, offsets, "
        "storage values, vectors, or provider data."
    ),
)
async def get_document_source_context(
    document_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    documents: DocumentServiceDependency,
    chunk_id: UUID,
) -> SuccessResponse[DocumentSourceContextData]:
    """Fetch context only on explicit demand; transport owns no policy decisions."""

    context = await documents.get_source_context(principal, document_id, chunk_id=chunk_id)
    return SuccessResponse(data=_source_context_data(context), meta=_meta(request))


@router.post(
    "/{document_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SuccessResponse[DocumentData],
    responses=_DOCUMENT_ERROR_RESPONSES,
    summary="Request asynchronous document reprocessing",
    description=(
        "Queues a metadata-only parse request for a terminal or pending document. It never accepts "
        "content, storage fields, or worker task arguments."
    ),
)
async def reprocess_document(
    document_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    documents: DocumentServiceDependency,
) -> SuccessResponse[DocumentData]:
    """Reset parser state while preserving old text until a replacement succeeds."""

    document = await documents.reprocess(principal, document_id)
    return SuccessResponse(data=_document_data(document), meta=_meta(request))


@router.post(
    "/{document_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SuccessResponse[DocumentData],
    responses=_DOCUMENT_ERROR_RESPONSES,
    summary="Request asynchronous document re-indexing",
    description=(
        "Queues a metadata-only replacement of retrieval chunks for an already parsed document. "
        "It accepts no content, embeddings, provider options, or worker identifiers and exposes "
        "no chunks or search results."
    ),
)
async def reindex_document(
    document_id: UUID,
    request: Request,
    principal: CurrentPrincipalDependency,
    documents: DocumentServiceDependency,
) -> SuccessResponse[DocumentData]:
    """Queue one authorized index lifecycle transition without exposing retrieval data."""

    document = await documents.reindex(principal, document_id)
    return SuccessResponse(data=_document_data(document), meta=_meta(request))


def _document_data(document: Document) -> DocumentData:
    """Build the deliberate public view without storage keys, checksums, or raw data."""

    assert document.case_id is not None
    return DocumentData(
        document_id=document.id,
        case_id=document.case_id,
        uploaded_by_user_id=document.uploaded_by_user_id,
        title=document.title,
        original_filename=document.original_filename,
        file_type=document.file_type,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        source_status=DocumentSourceStatus(document.source_status),
        confidentiality_level=DocumentConfidentialityLevel(document.confidentiality_level),
        parsing_status=DocumentParsingStatus(document.parsing_status),
        language=document.language,
        page_count=document.page_count,
        parsing_error=document.parsing_error,
        indexing_status=DocumentIndexingStatus(document.indexing_status or "not_ready"),
        indexing_error=document.indexing_error,
        indexed_at=document.indexed_at,
        inserted_at=document.inserted_at,
        updated_at=document.updated_at,
    )


def _source_context_data(context: DocumentSourceContext) -> DocumentSourceContextData:
    """Serialize only the deliberate presentation-safe context fields."""

    return DocumentSourceContextData(
        document_id=context.document_id,
        chunk_id=context.chunk_id,
        document_title=context.document_title,
        document_file_type=context.document_file_type,
        source_status=DocumentSourceStatus(context.source_status),
        page_number=context.page_number,
        section_title=context.section_title,
        context=context.context,
        truncated=context.truncated,
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
