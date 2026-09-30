"""Admin-only organization-scoped user and role management operations."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.dependencies import AdminPrincipalDependency, UserAdministrationServiceDependency
from app.api.schemas.common import (
    DEFAULT_ERROR_RESPONSES,
    ErrorResponse,
    ResponseMeta,
    SuccessResponse,
)
from app.api.schemas.users import (
    RoleData,
    RolesReplaceRequest,
    UserCreateRequest,
    UserData,
    UserListData,
    UserUpdateRequest,
)
from app.services.auth.principal import Principal, RoleName, canonical_roles
from app.services.auth.service import UserAdminAddCommand, UserAdminUpdateCommand
from app.services.common.pagination import Pagination
from app.services.common.querying import SortDirection, SortSpec

PREFIX = "/users"
TAG = "Users"
DESCRIPTION = "Admin-only organization-scoped user and role management."

router = APIRouter()
# Roles are owned by this module but architecture reserves their catalogue at
# ``/api/roles`` rather than beneath the user resource collection.
roles_router = APIRouter()

_USER_ERROR_RESPONSES = {
    **DEFAULT_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "Administrator access is required."},
}


@router.get(
    "",
    response_model=SuccessResponse[UserListData],
    responses=_USER_ERROR_RESPONSES,
    summary="List users in the current organization",
)
async def list_users(
    request: Request,
    principal: AdminPrincipalDependency,
    administration: UserAdministrationServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Literal["inserted_at", "email", "display_name"] = "inserted_at",
    direction: SortDirection = SortDirection.DESC,
) -> SuccessResponse[UserListData]:
    """List only tenant users through the existing bounded repository contract."""

    page = await administration.list_users(
        principal,
        pagination=Pagination(limit=limit, offset=offset),
        sort=SortSpec(key=sort, direction=direction),
    )
    items: tuple[UserData, ...] = tuple(
        [await _user_data(administration, principal, user.id) for user in page.items]
    )
    return SuccessResponse(
        data=UserListData(
            items=items,
            limit=page.limit,
            offset=page.offset,
            total=page.total,
            has_more=page.has_more,
        ),
        meta=_meta(request),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[UserData],
    responses=_USER_ERROR_RESPONSES,
    summary="Add a user in the current organization",
)
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    principal: AdminPrincipalDependency,
    administration: UserAdministrationServiceDependency,
) -> SuccessResponse[UserData]:
    """Add a local/passwordless user without accepting a caller organization ID."""

    user = await administration.add_user(
        principal,
        UserAdminAddCommand(
            email=payload.email,
            display_name=payload.display_name,
            preferred_language=payload.preferred_language,
            password=payload.password,
            role_names=payload.role_names,
        ),
    )
    return SuccessResponse(
        data=await _user_data(administration, principal, user.id), meta=_meta(request)
    )


@router.get(
    "/{user_id}",
    response_model=SuccessResponse[UserData],
    responses=_USER_ERROR_RESPONSES,
    summary="Get one user in the current organization",
)
async def get_user(
    user_id: UUID,
    request: Request,
    principal: AdminPrincipalDependency,
    administration: UserAdministrationServiceDependency,
) -> SuccessResponse[UserData]:
    """Resolve a target only through the caller's organization scope."""

    await administration.get_user(principal, user_id)
    return SuccessResponse(
        data=await _user_data(administration, principal, user_id), meta=_meta(request)
    )


@router.patch(
    "/{user_id}",
    response_model=SuccessResponse[UserData],
    responses=_USER_ERROR_RESPONSES,
    summary="Update a user in the current organization",
)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    request: Request,
    principal: AdminPrincipalDependency,
    administration: UserAdministrationServiceDependency,
) -> SuccessResponse[UserData]:
    """Update permitted fields, invalidating sessions for password/deactivation changes."""

    user = await administration.update_user(
        principal,
        user_id,
        UserAdminUpdateCommand(
            display_name=payload.display_name,
            preferred_language=payload.preferred_language,
            is_active=payload.is_active,
            password=payload.password,
        ),
    )
    return SuccessResponse(
        data=await _user_data(administration, principal, user.id), meta=_meta(request)
    )


@roles_router.get(
    "/roles",
    response_model=SuccessResponse[tuple[RoleData, ...]],
    responses=_USER_ERROR_RESPONSES,
    summary="List the canonical global role catalogue",
)
async def list_roles(
    request: Request,
    _principal: AdminPrincipalDependency,
    administration: UserAdministrationServiceDependency,
) -> SuccessResponse[tuple[RoleData, ...]]:
    """Return only the five canonical roles rather than arbitrary future/global roles."""

    roles = await administration.list_roles()
    data = tuple(
        RoleData(role_id=role.id, name=RoleName(role.name), description=role.description)
        for role in roles
        if role.name in {item.value for item in RoleName}
    )
    return SuccessResponse(data=data, meta=_meta(request))


@router.put(
    "/{user_id}/roles",
    response_model=SuccessResponse[UserData],
    responses=_USER_ERROR_RESPONSES,
    summary="Replace a user's canonical role assignments",
)
async def replace_roles(
    user_id: UUID,
    payload: RolesReplaceRequest,
    request: Request,
    principal: AdminPrincipalDependency,
    administration: UserAdministrationServiceDependency,
) -> SuccessResponse[UserData]:
    """Replace the role set with validated canonical role names only."""

    await administration.replace_roles(principal, user_id, payload.role_names)
    return SuccessResponse(
        data=await _user_data(administration, principal, user_id), meta=_meta(request)
    )


async def _user_data(
    administration: UserAdministrationServiceDependency, principal: Principal, user_id: UUID
) -> UserData:
    user = await administration.get_user(principal, user_id)
    role_names = await administration.role_names_for_user(principal, user.id)
    return UserData(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        roles=tuple(sorted(canonical_roles(role_names), key=str)),
    )


def _meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None)
    return ResponseMeta(request_id=request_id if isinstance(request_id, str) else None)
