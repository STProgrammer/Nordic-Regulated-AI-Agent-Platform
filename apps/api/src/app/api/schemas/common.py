"""Shared success and error response contracts for the API.

These models define the stable, versionable envelope that later feature phases
reuse for their endpoints. The error envelope is intentionally machine-readable
and safe: it never carries exception class names, tracebacks, internal paths, or
secret-bearing input. Public messages use neutral English for this backend phase;
Norwegian UI localization is owned by Phase 7.
"""

from pydantic import BaseModel, ConfigDict, Field


class ResponseMeta(BaseModel):
    """Non-sensitive metadata attached to a successful response."""

    model_config = ConfigDict(frozen=True)

    request_id: str | None = Field(
        default=None,
        description="Correlation id echoed from the response request-id header.",
    )


class SuccessResponse[DataT](BaseModel):
    """Standard envelope wrapping a typed success payload."""

    model_config = ConfigDict(frozen=True)

    data: DataT
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class ErrorDetail(BaseModel):
    """A single safe, field-level error detail for validation failures."""

    model_config = ConfigDict(frozen=True)

    field: str | None = Field(
        default=None,
        description="Dotted location of the offending field, when applicable.",
    )
    code: str | None = Field(
        default=None, description="Machine-readable detail code, when available."
    )
    message: str = Field(description="Safe, human-readable description of the problem.")


class ErrorBody(BaseModel):
    """The body of an error envelope."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(description="Stable, machine-readable error code.")
    message: str = Field(description="Safe, human-readable error message.")
    request_id: str | None = Field(
        default=None, description="Correlation id for this request, when available."
    )
    details: list[ErrorDetail] | None = Field(
        default=None,
        description="Optional safe field-level details, e.g. for validation errors.",
    )


class ErrorResponse(BaseModel):
    """Standard error envelope returned by every centralized error handler."""

    model_config = ConfigDict(frozen=True)

    error: ErrorBody


# Reusable OpenAPI ``responses`` declarations. They are applied only to real
# endpoints as those endpoints are implemented by their owning phases; the route
# modules added in Phase 3 intentionally expose no operations yet.
ErrorResponseSpec = dict[str, object]
ErrorResponses = dict[int | str, ErrorResponseSpec]

DEFAULT_ERROR_RESPONSES: ErrorResponses = {
    400: {"model": ErrorResponse, "description": "The request was invalid."},
    404: {"model": ErrorResponse, "description": "The resource was not found."},
    422: {"model": ErrorResponse, "description": "The request failed validation."},
    500: {"model": ErrorResponse, "description": "An unexpected error occurred."},
}
