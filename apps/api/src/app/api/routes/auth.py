"""Authentication and session HTTP operations owned by Phase 6."""

from __future__ import annotations

from agent_orchestrator.graphs.drafting_types import OutputLanguage
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.api.dependencies import (
    AuthenticationServiceDependency,
    ControlledMemoryServiceDependency,
    CurrentPrincipalDependency,
    LoginRateLimiterDependency,
    SettingsDependency,
)
from app.api.schemas.auth import (
    CurrentUserData,
    LanguagePreferenceRequest,
    LoginRequest,
    LogoutData,
)
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.core.errors import ApiError, error_response
from app.core.rate_limit import RateLimitDecision
from app.core.session_store import AuthStateUnavailableError
from app.services.auth.service import LoginCommand, LoginRejected, LoginSucceeded
from app.services.errors import MemoryStoreUnavailableError
from app.services.memory.service import MemoryStoreUnavailableError as MemoryStoreOperationError

PREFIX = "/auth"
TAG = "Auth"
DESCRIPTION = "Local password authentication, opaque sessions, and current-user lookup."

router = APIRouter()

_AUTH_ERROR_RESPONSES = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication failed or is required."},
    429: {"model": ErrorResponse, "description": "Too many login attempts."},
    503: {"model": ErrorResponse, "description": "Authentication state is unavailable."},
}


@router.post(
    "/login",
    response_model=SuccessResponse[CurrentUserData],
    responses=_AUTH_ERROR_RESPONSES,
    summary="Sign in with a local email and password",
)
async def login(
    payload: LoginRequest,
    request: Request,
    settings: SettingsDependency,
    rate_limiter: LoginRateLimiterDependency,
    authentication: AuthenticationServiceDependency,
) -> SuccessResponse[CurrentUserData] | JSONResponse:
    """Rate-limit and authenticate a local account without exposing account state."""

    try:
        decision = await rate_limiter.check(payload.email, _client_origin(request))
    except AuthStateUnavailableError:
        return _auth_unavailable_response(request)
    if not decision.allowed:
        return _rate_limited_response(request, decision)

    result = await authentication.login(
        LoginCommand(email=payload.email, password=payload.password)
    )
    if isinstance(result, LoginRejected):
        # Return rather than raise so a known-account failure's minimal audit row
        # commits with the caller-owned request transaction.
        return error_response(
            request=request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Invalid email or password.",
        )
    if not isinstance(result, LoginSucceeded):  # defensive exhaustiveness guard
        raise ApiError(
            status_code=500, code="internal_error", message="An unexpected error occurred."
        )

    body = SuccessResponse(
        data=_current_user_data(result.principal),
        meta=ResponseMeta(request_id=getattr(request.state, "request_id", None)),
    )
    response = JSONResponse(status_code=status.HTTP_200_OK, content=body.model_dump(mode="json"))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_id,
        max_age=settings.session_ttl_seconds,
        path=settings.session_cookie_path,
        domain=settings.session_cookie_domain,
        secure=settings.session_cookie_secure_value,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )
    return response


@router.post(
    "/logout",
    response_model=SuccessResponse[LogoutData],
    responses=_AUTH_ERROR_RESPONSES,
    summary="Invalidate the current opaque session",
)
async def logout(
    request: Request,
    settings: SettingsDependency,
    principal: CurrentPrincipalDependency,
    authentication: AuthenticationServiceDependency,
) -> SuccessResponse[LogoutData] | JSONResponse:
    """Delete the server-side session and matching browser cookie."""

    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id is None:  # CurrentPrincipal already rejects this; preserve a safe fallback.
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_required",
            message="Authentication is required.",
        )
    try:
        await authentication.logout(principal, session_id)
    except AuthStateUnavailableError as error:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="authentication_unavailable",
            message="Authentication is temporarily unavailable.",
        ) from error
    body = SuccessResponse(
        data=LogoutData(),
        meta=ResponseMeta(request_id=getattr(request.state, "request_id", None)),
    )
    response = JSONResponse(status_code=status.HTTP_200_OK, content=body.model_dump(mode="json"))
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
        domain=settings.session_cookie_domain,
        secure=settings.session_cookie_secure_value,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )
    return response


@router.get(
    "/me",
    response_model=SuccessResponse[CurrentUserData],
    responses=_AUTH_ERROR_RESPONSES,
    summary="Return the current authenticated principal",
)
async def me(
    request: Request, principal: CurrentPrincipalDependency
) -> SuccessResponse[CurrentUserData]:
    """Return current server-validated identity and role data."""

    return SuccessResponse(
        data=_current_user_data(principal),
        meta=ResponseMeta(request_id=getattr(request.state, "request_id", None)),
    )


@router.put(
    "/me/preferred-language",
    response_model=SuccessResponse[CurrentUserData],
    responses=_AUTH_ERROR_RESPONSES,
    summary="Update the current user's closed language preference",
)
async def update_preferred_language(
    payload: LanguagePreferenceRequest,
    request: Request,
    principal: CurrentPrincipalDependency,
    memory: ControlledMemoryServiceDependency,
) -> SuccessResponse[CurrentUserData]:
    """Synchronize the canonical account preference and governed user-memory record."""

    try:
        user = await memory.update_self_language(
            principal, language=OutputLanguage(payload.preferred_language)
        )
    except MemoryStoreOperationError as error:
        raise MemoryStoreUnavailableError() from error
    return SuccessResponse(
        data=CurrentUserData(
            user_id=principal.user_id,
            organization_id=principal.organization_id,
            display_name=principal.display_name,
            preferred_language=user.preferred_language,
            roles=tuple(sorted(principal.roles, key=str)),
        ),
        meta=ResponseMeta(request_id=getattr(request.state, "request_id", None)),
    )


def _current_user_data(principal: CurrentPrincipalDependency) -> CurrentUserData:
    return CurrentUserData(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        display_name=principal.display_name,
        preferred_language=principal.preferred_language,
        roles=tuple(sorted(principal.roles, key=str)),
    )


def _client_origin(request: Request) -> str:
    client = request.client
    return client.host if client is not None else "unknown-client"


def _rate_limited_response(request: Request, decision: RateLimitDecision) -> JSONResponse:
    retry_after = decision.retry_after_seconds if decision.retry_after_seconds is not None else 1
    return error_response(
        request=request,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="login_rate_limited",
        message="Too many login attempts. Try again later.",
        response_headers={"Retry-After": str(retry_after)},
    )


def _auth_unavailable_response(request: Request) -> JSONResponse:
    return error_response(
        request=request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="authentication_unavailable",
        message="Authentication is temporarily unavailable.",
    )
