"""Protected governed retrieval and direct, source-grounded RAG answering."""

from fastapi import APIRouter, Request

from app.api.dependencies import (
    CurrentPrincipalDependency,
    RagAnswerServiceDependency,
    RetrievalServiceDependency,
    RouteRateLimiterDependency,
    SettingsDependency,
)
from app.api.route_rate_limit import enforce_route_rate_limit
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.api.schemas.retrieval import (
    RetrievalAnswerData,
    RetrievalAnswerLanguage,
    RetrievalAnswerOutcome,
    RetrievalAnswerRequest,
    RetrievalCitationData,
    RetrievalEvidenceReason,
    RetrievalMethod,
    RetrievalSearchRequest,
    RetrievalSourceData,
    RetrievalSourceStatus,
    RetrievalWarningCode,
)
from app.core.rate_limit import RouteRateLimitPolicy
from app.services.retrieval.types import AnswerLanguage, RagAnswerCommand, RetrievalRequest

PREFIX = "/retrieval"
TAG = "Retrieval"
DESCRIPTION = (
    "Protected organization-scoped hybrid source search and direct answer generation. "
    "Search returns "
    "governed bounded excerpts; answers use only current approved sources and structural citations."
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
    429: {"model": ErrorResponse, "description": "The retrieval rate limit was reached."},
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
    settings: SettingsDependency,
    rate_limiter: RouteRateLimiterDependency,
) -> SuccessResponse[list[RetrievalSourceData]]:
    """Keep HTTP transport thin; policy, SQL, embeddings, and audit stay in the service."""

    await _enforce_retrieval_rate_limit(request, principal.user_id, rate_limiter, settings)

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


@router.post(
    "/answer",
    response_model=SuccessResponse[RetrievalAnswerData],
    responses={
        **_RETRIEVAL_ERROR_RESPONSES,
        503: {
            "model": ErrorResponse,
            "description": "Answer generation is temporarily unavailable.",
        },
    },
    summary="Answer from current approved sources for one readable case",
    description=(
        "Uses governed hybrid retrieval with approved sources only. A successful response is "
        "either a bounded answer with validated inline [S#] citations or a safe "
        "needs-more-evidence refusal."
    ),
)
async def answer_retrieval_question(
    payload: RetrievalAnswerRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    answering: RagAnswerServiceDependency,
    settings: SettingsDependency,
    rate_limiter: RouteRateLimiterDependency,
) -> SuccessResponse[RetrievalAnswerData]:
    """Keep HTTP transport thin; policy, evidence, generation, and records stay in the service."""

    await _enforce_retrieval_rate_limit(request, principal.user_id, rate_limiter, settings)

    result = await answering.answer(
        principal,
        RagAnswerCommand(
            case_id=payload.case_id,
            question=payload.question,
            answer_language=(
                AnswerLanguage(payload.answer_language.value)
                if payload.answer_language is not None
                else None
            ),
        ),
    )
    return SuccessResponse(
        data=RetrievalAnswerData(
            run_id=result.run_id,
            outcome=RetrievalAnswerOutcome(result.outcome.value),
            language=RetrievalAnswerLanguage(result.language.value),
            answer=result.answer,
            citations=tuple(
                RetrievalCitationData(
                    label=citation.label,
                    document_id=citation.document_id,
                    document_title=citation.document_title,
                    document_file_type=citation.document_file_type,
                    chunk_id=citation.chunk_id,
                    page_number=citation.page_number,
                    section_title=citation.section_title,
                    excerpt=citation.excerpt,
                    rank=citation.rank,
                    retrieval_methods=tuple(
                        RetrievalMethod(method.value) for method in citation.retrieval_methods
                    ),
                )
                for citation in result.citations
            ),
            evidence_reason=(
                RetrievalEvidenceReason(result.evidence_reason.value)
                if result.evidence_reason is not None
                else None
            ),
        ),
        meta=_meta(request),
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)


async def _enforce_retrieval_rate_limit(
    request: Request,
    user_id: object,
    rate_limiter: RouteRateLimiterDependency,
    settings: SettingsDependency,
) -> None:
    await enforce_route_rate_limit(
        request,
        rate_limiter,
        RouteRateLimitPolicy(
            bucket="retrieval",
            user_attempts=settings.retrieval_rate_limit_user_attempts,
            origin_attempts=settings.retrieval_rate_limit_origin_attempts,
            window_seconds=settings.retrieval_rate_limit_window_seconds,
        ),
        user_id=str(user_id),
    )
