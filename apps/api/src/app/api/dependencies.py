"""Shared FastAPI dependencies for database, authentication, and RBAC boundaries."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppSettings, get_settings
from app.core.errors import ApiError
from app.core.rate_limit import LoginRateLimiter, RedisLoginRateLimiter
from app.core.security import PasswordSecurity
from app.core.session_store import (
    AuthStateUnavailableError,
    RedisSessionStore,
    SessionStore,
    get_redis_client,
)
from app.db.session import get_db_session
from app.services.auth.policy import ensure_roles, guard_tenant_resource
from app.services.auth.principal import Principal, RoleName
from app.services.auth.service import AuthenticationService, UserAdministrationService
from app.services.cases.service import CaseService
from app.services.documents.dispatch import CeleryDocumentTaskDispatcher
from app.services.documents.embeddings import build_embedding_provider
from app.services.documents.service import DocumentService
from app.services.documents.storage import AzureBlobObjectStorage, ObjectStorage
from app.services.errors import StorageUnavailableError
from app.services.retrieval.answering import RagAnswerService
from app.services.retrieval.generator import build_rag_answer_generator
from app.services.retrieval.service import RetrievalService

# The runtime setting defaults to this name. The dependency itself reads the
# configured cookie name, while this object documents cookie authentication in
# OpenAPI and tells generated clients it is HTTP cookie based rather than bearer.
session_cookie_security_scheme = APIKeyCookie(
    name="nordic_session",
    scheme_name="SessionCookie",
    description="Opaque HTTP-only server-side session cookie.",
    auto_error=False,
)


def get_request_id(request: Request) -> str | None:
    """Return the correlation id bound to the request by the context middleware."""

    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else None


def get_session_store(settings: Annotated[AppSettings, Depends(get_settings)]) -> SessionStore:
    """Build the production session-store adapter without touching Redis yet."""

    return RedisSessionStore(get_redis_client(settings))


def get_login_rate_limiter(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> LoginRateLimiter:
    """Build the login limiter; only its ``check`` call connects to Redis."""

    return RedisLoginRateLimiter(
        get_redis_client(settings),
        digest_key=settings.rate_limit_hmac_key(),
        email_attempts=settings.login_rate_limit_email_attempts,
        origin_attempts=settings.login_rate_limit_origin_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )


def get_authentication_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    session_store: Annotated[SessionStore, Depends(get_session_store)],
) -> AuthenticationService:
    """Construct the request-scoped authentication service."""

    return AuthenticationService(
        session,
        password_security=PasswordSecurity(
            minimum_length=settings.password_min_length,
            maximum_length=settings.password_max_length,
        ),
        session_store=session_store,
        session_ttl_seconds=settings.session_ttl_seconds,
    )


def get_user_administration_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    session_store: Annotated[SessionStore, Depends(get_session_store)],
) -> UserAdministrationService:
    """Construct the request-scoped Admin user-management service."""

    return UserAdministrationService(
        session,
        password_security=PasswordSecurity(
            minimum_length=settings.password_min_length,
            maximum_length=settings.password_max_length,
        ),
        session_store=session_store,
    )


def get_case_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CaseService:
    """Construct the request-scoped Case Management domain service."""

    return CaseService(session)


async def get_object_storage(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> AsyncIterator[ObjectStorage]:
    """Provide one private Azure Blob-compatible adapter for the request lifetime."""

    try:
        storage = AzureBlobObjectStorage(
            connection_string=settings.object_storage_connection_string_value(),
            container=settings.object_storage_container,
        )
    except Exception as error:
        raise StorageUnavailableError() from error
    try:
        yield storage
    finally:
        await storage.close()


def get_document_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> DocumentService:
    """Construct the single request-scoped secure document-upload coordinator."""

    return DocumentService(
        session,
        storage=storage,
        maximum_upload_bytes=settings.document_upload_max_bytes,
        dispatcher=CeleryDocumentTaskDispatcher(),
        maximum_context_characters=settings.document_context_max_characters,
    )


def get_retrieval_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> RetrievalService:
    """Construct Phase 13 retrieval without creating a provider client eagerly."""

    return RetrievalService(
        session,
        provider_factory=lambda: build_embedding_provider(settings),
        default_result_limit=settings.retrieval_default_result_limit,
        maximum_result_limit=settings.retrieval_max_result_limit,
        semantic_candidate_limit=settings.retrieval_semantic_candidate_limit,
        keyword_candidate_limit=settings.retrieval_keyword_candidate_limit,
        rank_fusion_constant=settings.retrieval_rank_fusion_constant,
        maximum_query_characters=settings.retrieval_max_query_characters,
        maximum_document_selections=settings.retrieval_max_document_selections,
        maximum_excerpt_characters=settings.retrieval_max_excerpt_characters,
    )


def get_rag_answer_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    retrieval: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> RagAnswerService:
    """Construct direct RAG answering without eagerly creating a provider client."""

    return RagAnswerService(
        session,
        retrieval=retrieval,
        generator_factory=lambda: build_rag_answer_generator(settings),
        maximum_answer_characters=settings.rag_max_answer_characters,
        maximum_evidence_sources=settings.rag_max_evidence_sources,
        maximum_evidence_characters=settings.rag_max_evidence_characters,
        minimum_evidence_sources=settings.rag_min_evidence_sources,
        minimum_evidence_characters=settings.rag_min_evidence_characters,
        input_price_per_million=settings.rag_input_price_per_million,
        output_price_per_million=settings.rag_output_price_per_million,
    )


async def get_current_principal(
    request: Request,
    settings: Annotated[AppSettings, Depends(get_settings)],
    authentication: Annotated[AuthenticationService, Depends(get_authentication_service)],
    _documented_session: Annotated[str | None, Security(session_cookie_security_scheme)] = None,
) -> Principal:
    """Resolve and validate a principal from an opaque session cookie."""

    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id is None or len(session_id) > 128:
        raise _unauthenticated_error()
    try:
        principal = await authentication.resolve_principal(session_id)
    except AuthStateUnavailableError as error:
        raise _auth_state_unavailable_error() from error
    if principal is None:
        raise _unauthenticated_error()
    return principal


def require_roles(*roles: RoleName) -> Callable[[Principal], Awaitable[Principal]]:
    """Return a composable backend role-check dependency for protected routes."""

    async def _require(principal: CurrentPrincipalDependency) -> Principal:
        ensure_roles(principal, *roles)
        return principal

    return _require


def guard_current_tenant(principal: Principal, resource_organization_id: UUID) -> None:
    """Expose the pure tenant guard for future service/route composition."""

    guard_tenant_resource(principal, resource_organization_id)


def _unauthenticated_error() -> ApiError:
    return ApiError(
        status_code=401,
        code="authentication_required",
        message="Authentication is required.",
    )


def _auth_state_unavailable_error() -> ApiError:
    return ApiError(
        status_code=503,
        code="authentication_unavailable",
        message="Authentication is temporarily unavailable.",
    )


SettingsDependency = Annotated[AppSettings, Depends(get_settings)]
RequestIdDependency = Annotated[str | None, Depends(get_request_id)]
DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
SessionStoreDependency = Annotated[SessionStore, Depends(get_session_store)]
LoginRateLimiterDependency = Annotated[LoginRateLimiter, Depends(get_login_rate_limiter)]
AuthenticationServiceDependency = Annotated[
    AuthenticationService, Depends(get_authentication_service)
]
UserAdministrationServiceDependency = Annotated[
    UserAdministrationService, Depends(get_user_administration_service)
]
CaseServiceDependency = Annotated[CaseService, Depends(get_case_service)]
ObjectStorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]
DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
RetrievalServiceDependency = Annotated[RetrievalService, Depends(get_retrieval_service)]
RagAnswerServiceDependency = Annotated[RagAnswerService, Depends(get_rag_answer_service)]
CurrentPrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
AdminPrincipalDependency = Annotated[Principal, Depends(require_roles(RoleName.ADMIN))]
