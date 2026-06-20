"""Centralized API error types and safe exception handlers.

Every error path the application can produce is funneled through one of these
handlers so clients always receive the same stable :class:`ErrorResponse` envelope.
Responses never expose exception class names, tracebacks, internal paths, request
bodies, or secret-bearing values. Public messages use neutral English for this
backend phase; Norwegian UI localization is owned by Phase 7.
"""

import http
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.api.schemas.common import ErrorBody, ErrorDetail, ErrorResponse
from app.core.logging import get_logger
from app.services.errors import (
    AuthorizationDeniedError,
    ConflictError,
    InvalidCommandError,
    NotFoundError,
    ServiceError,
)

_logger = get_logger("api.error")

_UNEXPECTED_ERROR_CODE = "internal_error"
_UNEXPECTED_ERROR_MESSAGE = "An unexpected error occurred."
_VALIDATION_ERROR_CODE = "validation_error"
_VALIDATION_ERROR_MESSAGE = "The request failed validation."


class ApiError(Exception):
    """Base type for expected, client-facing API errors.

    Subclasses or call sites supply a deliberate status code, a stable machine
    ``code``, a safe public ``message``, and optional safe field-level ``details``.
    """

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _request_id(request: Request) -> str | None:
    """Read the correlation id bound to the request by the context middleware."""

    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else None


def _request_id_header(request: Request) -> str:
    """Read the configured request-id header name from application state."""

    header_name = getattr(request.app.state, "request_id_header", None)
    return header_name if isinstance(header_name, str) else "X-Request-ID"


def error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    response_headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the standard JSON error envelope for a failed request.

    The correlation id is written to both the body and the response header so it is
    present even when the outermost error path produces the response.
    """

    request_id = _request_id(request)
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=request_id,
            details=details,
        )
    )
    headers = dict(response_headers) if response_headers is not None else {}
    if request_id:
        headers[_request_id_header(request)] = request_id
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=headers or None,
    )


def _http_error_code(status_code: int) -> str:
    try:
        return http.HTTPStatus(status_code).name.lower()
    except ValueError:
        return "http_error"


def _http_error_message(status_code: int) -> str:
    try:
        return http.HTTPStatus(status_code).phrase
    except ValueError:
        return "Request could not be completed."


async def _handle_api_error(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, ApiError):  # defensive: only registered for ApiError
        raise exc
    return error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def _handle_validation_error(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, RequestValidationError):  # defensive narrowing
        raise exc
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            code=str(error["type"]),
            message=str(error["msg"]),
        )
        for error in exc.errors()
    ]
    return error_response(
        request=request,
        status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY,
        code=_VALIDATION_ERROR_CODE,
        message=_VALIDATION_ERROR_MESSAGE,
        details=details,
    )


async def _handle_http_exception(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, StarletteHTTPException):  # defensive narrowing
        raise exc
    return error_response(
        request=request,
        status_code=exc.status_code,
        code=_http_error_code(exc.status_code),
        message=_http_error_message(exc.status_code),
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> Response:
    # Log the failure server-side for operators (including the exception type) but
    # never serialize any exception detail into the client response.
    _logger.error(
        "request.unhandled_error",
        error_type=type(exc).__name__,
        request_id=_request_id(request),
    )
    return error_response(
        request=request,
        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR,
        code=_UNEXPECTED_ERROR_CODE,
        message=_UNEXPECTED_ERROR_MESSAGE,
    )


async def _handle_service_error(request: Request, exc: Exception) -> Response:
    """Translate deliberate service-layer errors without exposing implementation detail."""

    if not isinstance(exc, ServiceError):  # defensive narrowing for the registry
        raise exc
    if isinstance(exc, NotFoundError):
        status_code = http.HTTPStatus.NOT_FOUND
    elif isinstance(exc, ConflictError):
        status_code = http.HTTPStatus.CONFLICT
    elif isinstance(exc, AuthorizationDeniedError):
        status_code = http.HTTPStatus.FORBIDDEN
    elif isinstance(exc, InvalidCommandError):
        status_code = http.HTTPStatus.UNPROCESSABLE_ENTITY
    else:
        status_code = http.HTTPStatus.BAD_REQUEST
    return error_response(
        request=request,
        status_code=status_code,
        code=exc.code,
        message=exc.message,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers on the application."""

    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(ServiceError, _handle_service_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
