"""Protected governed source search; answers and citations remain future work."""

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentPrincipalDependency, RetrievalServiceDependency
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.api.schemas.retrieval import (
    RetrievalMethod,
    RetrievalSearchRequest,
    RetrievalSourceData,
    RetrievalSourceStatus,
    RetrievalWarningCode,
)
from app.services.retrieval.types import RetrievalRequest

PREFIX = "/retrieval"
TAG = "Retrieval"
DESCRIPTION = (
    "Protected organization-scoped hybrid source search. It returns governed, bounded source "
    "excerpts only; answer generation and citations remain future-phase work."
)

router = APIRouter()

_RETRIEVAL_ERROR_RESPONSES = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {
        "model": ErrorResponse,
        "description": "The current role or source entitlement is not allowed.",
    },
    404: {"model": ErrorResponse, "description": "The case or selected document was not found."},
    503: {"model": ErrorResponse, "description": "Retrieval is temporarily unavailable."},
}


@router.post(
    "/search",
    response_model=SuccessResponse[list[RetrievalSourceData]],
    responses=_RETRIEVAL_ERROR_RESPONSES,
    summary="Search current permitted document sources for one readable case",
    description=(
        "Uses one validated query embedding plus PostgreSQL full-text search, then deterministic "
        "rank fusion. It never returns raw documents, full chunks, vectors, citations, answers, "
        "or confidence decisions."
    ),
)
async def search_retrieval_sources(
    payload: RetrievalSearchRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    retrieval: RetrievalServiceDependency,
) -> SuccessResponse[list[RetrievalSourceData]]:
    """Keep HTTP transport thin; policy, SQL, embeddings, and audit stay in the service."""

    sources = await retrieval.search(
        principal,
        RetrievalRequest(
            case_id=payload.case_id,
            query=payload.query,
            result_limit=payload.limit,
            source_statuses=tuple(status.value for status in payload.source_statuses or ()),
            document_ids=payload.document_ids or (),
        ),
    )
    return SuccessResponse(
        data=[
            RetrievalSourceData(
                document_id=source.document_id,
                document_title=source.document_title,
                document_file_type=source.document_file_type,
                chunk_id=source.chunk_id,
                page_number=source.page_number,
                section_title=source.section_title,
                source_status=RetrievalSourceStatus(source.source_status),
                rank=source.rank,
                rank_score=source.rank_score,
                retrieval_methods=tuple(
                    RetrievalMethod(method.value) for method in source.retrieval_methods
                ),
                excerpt=source.excerpt,
                warning_codes=tuple(
                    RetrievalWarningCode(code.value) for code in source.warning_codes
                ),
            )
            for source in sources
        ],
        meta=_meta(request),
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
