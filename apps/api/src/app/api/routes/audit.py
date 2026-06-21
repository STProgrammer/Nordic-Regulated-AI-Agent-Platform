"""Read-only audit-event inspection API boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import AuditServiceDependency, CurrentPrincipalDependency
from app.api.schemas.audit import AuditEventData, AuditEventListData
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.db.models.audit import AuditEvent
from app.db.repositories.audit import AuditEventFilters
from app.services.common.pagination import Page, Pagination
from app.services.errors import InvalidQueryError
from app.services.workflows.trace_safety import sanitize_metadata

PREFIX = "/audit"
TAG = "Audit"
DESCRIPTION = (
    "Read-only tenant audit-event inspection. Workflow traces are available from the Workflows "
    "boundary and never expose prompts, content, credentials, or transport metadata."
)

router = APIRouter()

_AUDIT_ERRORS = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "The current role is not allowed."},
}


@router.get(
    "/events",
    response_model=SuccessResponse[AuditEventListData],
    responses=_AUDIT_ERRORS,
    summary="List immutable audit events for the authenticated organization",
)
async def list_audit_events(
    request: Request,
    principal: CurrentPrincipalDependency,
    audit: AuditServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    case_id: UUID | None = None,
    resource_type: Annotated[str | None, Query(max_length=100)] = None,
    event_type: Annotated[str | None, Query(max_length=100)] = None,
    inserted_after: datetime | None = None,
    inserted_before: datetime | None = None,
) -> SuccessResponse[AuditEventListData]:
    """Filter only within the cookie principal's tenant; organization is never caller-selected."""

    after, before = _utc_range(inserted_after, inserted_before)
    page = await audit.list_for_principal(
        principal,
        pagination=Pagination(limit=limit, offset=offset),
        filters=AuditEventFilters(
            case_id=case_id,
            resource_type=_filter_value(resource_type),
            event_type=_filter_value(event_type),
            inserted_after=after,
            inserted_before=before,
        ),
    )
    return SuccessResponse(data=audit_page_data(page), meta=_meta(request))


def audit_event_data(event: AuditEvent) -> AuditEventData:
    """Map a stored append-only event through the response-side metadata sanitizer."""

    return AuditEventData(
        event_id=event.id,
        event_type=event.event_type,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        case_id=event.case_id,
        actor_user_id=event.actor_user_id,
        inserted_at=event.inserted_at,
        metadata=sanitize_metadata(event.event_data),
    )


def audit_page_data(page: Page[AuditEvent]) -> AuditEventListData:
    return AuditEventListData(
        items=tuple(audit_event_data(event) for event in page.items),
        limit=page.limit,
        offset=page.offset,
        total=page.total,
        has_more=page.has_more,
    )


def _utc_range(
    inserted_after: datetime | None, inserted_before: datetime | None
) -> tuple[datetime | None, datetime | None]:
    for value in (inserted_after, inserted_before):
        invalid_utc = value is not None and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        )
        if invalid_utc:
            raise InvalidQueryError("Audit timestamps must use a UTC offset.")
    if (
        inserted_after is not None
        and inserted_before is not None
        and inserted_after > inserted_before
    ):
        raise InvalidQueryError("The audit timestamp range is invalid.")
    return inserted_after, inserted_before


def _filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise InvalidQueryError("Audit filters must not be blank.")
    return normalized


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
