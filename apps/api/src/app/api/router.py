"""Aggregate product API router and its single source-of-truth route registry.

``ROUTE_GROUPS`` is the authoritative list of product API boundaries. Tests assert
its completeness and prefix/tag uniqueness so feature phases extend the existing
routers instead of introducing competing top-level paths. The route modules expose
no operations in Phase 3; this file only mounts their stable boundaries.
"""

from dataclasses import dataclass

from fastapi import APIRouter

from app.api.routes import (
    admin,
    approvals,
    audit,
    auth,
    cases,
    documents,
    evaluations,
    retrieval,
    users,
    workflows,
)


@dataclass(frozen=True)
class RouteGroup:
    """One product API boundary: its name, mount prefix, OpenAPI tag, and router."""

    name: str
    prefix: str
    tag: str
    description: str
    router: APIRouter


ROUTE_GROUPS: tuple[RouteGroup, ...] = (
    RouteGroup("auth", auth.PREFIX, auth.TAG, auth.DESCRIPTION, auth.router),
    RouteGroup("users", users.PREFIX, users.TAG, users.DESCRIPTION, users.router),
    RouteGroup("cases", cases.PREFIX, cases.TAG, cases.DESCRIPTION, cases.router),
    RouteGroup(
        "documents",
        documents.PREFIX,
        documents.TAG,
        documents.DESCRIPTION,
        documents.router,
    ),
    RouteGroup(
        "workflows",
        workflows.PREFIX,
        workflows.TAG,
        workflows.DESCRIPTION,
        workflows.router,
    ),
    RouteGroup(
        "approvals",
        approvals.PREFIX,
        approvals.TAG,
        approvals.DESCRIPTION,
        approvals.router,
    ),
    RouteGroup(
        "retrieval",
        retrieval.PREFIX,
        retrieval.TAG,
        retrieval.DESCRIPTION,
        retrieval.router,
    ),
    RouteGroup(
        "evaluations",
        evaluations.PREFIX,
        evaluations.TAG,
        evaluations.DESCRIPTION,
        evaluations.router,
    ),
    RouteGroup("audit", audit.PREFIX, audit.TAG, audit.DESCRIPTION, audit.router),
    RouteGroup("admin", admin.PREFIX, admin.TAG, admin.DESCRIPTION, admin.router),
)


def create_api_router(prefix: str) -> APIRouter:
    """Build the aggregate API router that mounts every product route group."""

    api_router = APIRouter(prefix=prefix)
    for group in ROUTE_GROUPS:
        api_router.include_router(group.router, prefix=group.prefix, tags=[group.tag])
    return api_router


def openapi_tags() -> list[dict[str, str]]:
    """Return OpenAPI tag metadata describing each product API boundary."""

    return [{"name": group.tag, "description": group.description} for group in ROUTE_GROUPS]
