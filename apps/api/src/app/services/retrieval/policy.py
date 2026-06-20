"""Pure source-governance scope resolution for retrieval."""

from __future__ import annotations

from uuid import UUID

from app.services.auth.policy import has_restricted_source_entitlement
from app.services.auth.principal import Principal
from app.services.errors import AuthorizationDeniedError, InvalidCommandError
from app.services.retrieval.types import RetrievalScope

_ALL_SOURCE_STATUSES = frozenset({"approved", "draft", "deprecated", "restricted", "archived"})
_RESTRICTED_SOURCE_STATUSES = frozenset({"restricted", "archived"})


def resolve_source_scope(
    principal: Principal,
    *,
    requested_statuses: tuple[str, ...],
    document_ids: tuple[UUID, ...],
) -> RetrievalScope:
    """Resolve defaults and entitlements before candidate SQL is constructed."""

    statuses = requested_statuses or ("approved",)
    if not set(statuses).issubset(_ALL_SOURCE_STATUSES):
        raise InvalidCommandError("The requested source statuses are invalid.")
    if len(set(statuses)) != len(statuses):
        raise InvalidCommandError("The requested source statuses must be unique.")
    if "archived" in statuses and not document_ids:
        raise InvalidCommandError("Archived sources require an explicit document selection.")
    restricted_entitled = has_restricted_source_entitlement(principal)
    if set(statuses).intersection(_RESTRICTED_SOURCE_STATUSES) and not restricted_entitled:
        raise AuthorizationDeniedError()
    return RetrievalScope(
        organization_id=principal.organization_id,
        source_statuses=statuses,
        document_ids=document_ids,
        restricted_entitled=restricted_entitled,
    )
