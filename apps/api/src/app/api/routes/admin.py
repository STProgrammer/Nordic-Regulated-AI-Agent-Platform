"""Admin-owned controlled-memory settings and inspectable typed entries."""

from __future__ import annotations

from uuid import UUID

from agent_orchestrator.memory.policy import (
    MemoryOrigin,
    MemoryPolicyError,
    MemoryScope,
    MemoryType,
)
from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import AdminPrincipalDependency, ControlledMemoryServiceDependency
from app.api.schemas.admin import (
    MemoryEntryData,
    MemoryEntryListData,
    MemorySettingsData,
    MemorySettingsUpdateRequest,
    OrganizationMemoryEntryCreateRequest,
    OrganizationMemoryEntryRevisionRequest,
)
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.db.models.memory import MemoryEntry
from app.services.errors import InvalidCommandError, MemoryStoreUnavailableError
from app.services.memory.service import (
    MemoryEntryCreate,
    MemoryEntryRevision,
)
from app.services.memory.service import (
    MemoryStoreUnavailableError as MemoryStoreOperationError,
)

PREFIX = "/admin"
TAG = "Admin"
DESCRIPTION = "Administrative controlled-memory settings and safe entry inspection."

router = APIRouter()

_MEMORY_ERRORS = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Administrator access is required."},
    503: {"model": ErrorResponse, "description": "Controlled memory is unavailable."},
}


@router.get(
    "/memory/settings",
    response_model=SuccessResponse[MemorySettingsData],
    responses=_MEMORY_ERRORS,
    summary="Read controlled-memory enablement for the current organization",
)
async def get_memory_settings(
    request: Request,
    principal: AdminPrincipalDependency,
    memory: ControlledMemoryServiceDependency,
) -> SuccessResponse[MemorySettingsData]:
    return SuccessResponse(
        data=MemorySettingsData(
            enabled=await memory.enabled_for_organization(principal.organization_id)
        ),
        meta=_meta(request),
    )


@router.put(
    "/memory/settings",
    response_model=SuccessResponse[MemorySettingsData],
    responses=_MEMORY_ERRORS,
    summary="Enable or disable controlled-memory use for the current organization",
)
async def update_memory_settings(
    payload: MemorySettingsUpdateRequest,
    request: Request,
    principal: AdminPrincipalDependency,
    memory: ControlledMemoryServiceDependency,
) -> SuccessResponse[MemorySettingsData]:
    enabled = await memory.set_enabled(principal, enabled=payload.enabled)
    return SuccessResponse(data=MemorySettingsData(enabled=enabled), meta=_meta(request))


@router.get(
    "/memory/entries",
    response_model=SuccessResponse[MemoryEntryListData],
    responses=_MEMORY_ERRORS,
    summary="List safe organization-level controlled-memory entries",
)
async def list_memory_entries(
    request: Request,
    principal: AdminPrincipalDependency,
    memory: ControlledMemoryServiceDependency,
    include_archived: bool = Query(default=False),
) -> SuccessResponse[MemoryEntryListData]:
    entries = await memory.list_organization_entries(principal, include_archived=include_archived)
    return SuccessResponse(
        data=MemoryEntryListData(items=tuple(_entry_data(entry) for entry in entries)),
        meta=_meta(request),
    )


@router.post(
    "/memory/entries",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[MemoryEntryData],
    responses=_MEMORY_ERRORS,
    summary="Create one safe organization-level controlled-memory entry",
)
async def create_memory_entry(
    payload: OrganizationMemoryEntryCreateRequest,
    request: Request,
    principal: AdminPrincipalDependency,
    memory: ControlledMemoryServiceDependency,
) -> SuccessResponse[MemoryEntryData]:
    try:
        entry = await memory.create_organization_entry(
            principal, MemoryEntryCreate(memory_type=payload.memory_type, content=payload.content)
        )
    except MemoryPolicyError as error:
        await memory.record_rejected_write(
            principal, memory_type=payload.memory_type, reason_code=error.reason_code
        )
        raise InvalidCommandError("The controlled-memory entry is not allowed.") from error
    except MemoryStoreOperationError as error:
        raise MemoryStoreUnavailableError() from error
    return SuccessResponse(data=_entry_data(entry), meta=_meta(request))


@router.put(
    "/memory/entries/{memory_entry_id}",
    response_model=SuccessResponse[MemoryEntryData],
    responses=_MEMORY_ERRORS,
    summary="Revise one safe organization-level controlled-memory entry",
)
async def revise_memory_entry(
    memory_entry_id: UUID,
    payload: OrganizationMemoryEntryRevisionRequest,
    request: Request,
    principal: AdminPrincipalDependency,
    memory: ControlledMemoryServiceDependency,
) -> SuccessResponse[MemoryEntryData]:
    try:
        entry = await memory.revise_organization_entry(
            principal, memory_entry_id, MemoryEntryRevision(content=payload.content)
        )
    except MemoryPolicyError as error:
        await memory.record_rejected_write(
            principal, memory_type=MemoryType.PROCESS_HINT, reason_code=error.reason_code
        )
        raise InvalidCommandError("The controlled-memory entry is not allowed.") from error
    except MemoryStoreOperationError as error:
        raise MemoryStoreUnavailableError() from error
    return SuccessResponse(data=_entry_data(entry), meta=_meta(request))


@router.post(
    "/memory/entries/{memory_entry_id}/archive",
    response_model=SuccessResponse[MemoryEntryData],
    responses=_MEMORY_ERRORS,
    summary="Archive one organization-level controlled-memory entry",
)
async def archive_memory_entry(
    memory_entry_id: UUID,
    request: Request,
    principal: AdminPrincipalDependency,
    memory: ControlledMemoryServiceDependency,
) -> SuccessResponse[MemoryEntryData]:
    try:
        entry = await memory.archive_organization_entry(principal, memory_entry_id)
    except MemoryStoreOperationError as error:
        raise MemoryStoreUnavailableError() from error
    return SuccessResponse(data=_entry_data(entry), meta=_meta(request))


def _entry_data(entry: MemoryEntry) -> MemoryEntryData:
    return MemoryEntryData(
        memory_entry_id=entry.id,
        memory_scope=MemoryScope(entry.memory_scope),
        memory_type=MemoryType(entry.memory_type),
        content=entry.content,
        source=MemoryOrigin(entry.source),
        is_active=entry.is_active,
        archived_at=entry.archived_at,
        inserted_at=entry.inserted_at,
        updated_at=entry.updated_at,
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
