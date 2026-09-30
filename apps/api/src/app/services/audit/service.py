"""Explicit, append-only audit event service with safe JSON metadata validation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent
from app.db.repositories.audit import AuditEventFilters, AuditEventRepository
from app.db.repositories.case import CaseRepository
from app.db.repositories.identity import UserRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.common.querying import SortSpec
from app.services.errors import InvalidCommandError, NotFoundError

if TYPE_CHECKING:
    from app.services.auth.principal import Principal

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

_FORBIDDEN_DATA_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "credentials",
        "password",
        "request_body",
        "secret",
        "token",
        "query",
        "query_hash",
        "query_text",
        "excerpt",
        "chunk_id",
        "embedding",
        "vector",
        "score",
        "checksum",
        "storage_key",
        "provider_response",
        "exception",
        "sql",
    }
)


@dataclass(frozen=True)
class AuditEventInput:
    """Deliberate audit event input; no request objects or raw exceptions are accepted."""

    organization_id: UUID
    event_type: str
    resource_type: str
    resource_id: UUID | None = None
    actor_user_id: UUID | None = None
    case_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    event_data: dict[str, JSONValue] = field(default_factory=dict)
    include_archived_case: bool = False


def _safe_json(value: JSONValue) -> JSONValue:
    """Copy JSON-safe data while rejecting secrets, non-finite numbers, and objects."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidCommandError("Audit event data must contain JSON-safe values.")
        return value
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    if isinstance(value, dict):
        clean: dict[str, JSONValue] = {}
        for key, item in value.items():
            if key.casefold() in _FORBIDDEN_DATA_KEYS:
                raise InvalidCommandError("Audit event data contains a prohibited field.")
            clean[key] = _safe_json(item)
        return clean
    raise InvalidCommandError("Audit event data must contain JSON-safe values.")


class AuditService:
    """Write audit events only when a product action explicitly asks for one."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AuditEventRepository(session)
        self.cases = CaseRepository(session)
        self.users = UserRepository(session)

    async def record_event(self, command: AuditEventInput) -> AuditEvent:
        """Append one validated event after all tenant-bound references are scoped."""

        if not command.event_type.strip() or not command.resource_type.strip():
            raise InvalidCommandError("Audit event and resource types are required.")
        if (
            command.actor_user_id is not None
            and await self.users.get(command.organization_id, command.actor_user_id) is None
        ):
            raise NotFoundError("User")
        if (
            command.case_id is not None
            and await self.cases.get(
                command.organization_id,
                command.case_id,
                include_archived=command.include_archived_case,
            )
            is None
        ):
            raise NotFoundError("Case")
        event_data = _safe_json(command.event_data)
        if not isinstance(event_data, dict):  # guarded by the typed command; keeps ORM input exact
            raise InvalidCommandError("Audit event data must be an object.")
        event = AuditEvent(
            organization_id=command.organization_id,
            event_type=command.event_type,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            actor_user_id=command.actor_user_id,
            case_id=command.case_id,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
            event_data=event_data,
        )
        return await stage_write(
            self.session,
            lambda: self.repository.append(event),
            resource="Audit event",
        )

    async def get_required(self, organization_id: UUID, event_id: UUID) -> AuditEvent:
        event = await self.repository.get(organization_id, event_id)
        if event is None:
            raise NotFoundError("Audit event")
        return event

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        filters: AuditEventFilters | None = None,
        sort: SortSpec | None = None,
    ) -> Page[AuditEvent]:
        return await self.repository.list(
            organization_id,
            pagination=pagination,
            filters=filters,
            sort=sort,
        )

    async def list_for_principal(
        self,
        principal: Principal,
        *,
        pagination: Pagination,
        filters: AuditEventFilters | None = None,
    ) -> Page[AuditEvent]:
        """List tenant-wide immutable events only for a dedicated audit role."""

        from app.services.auth.policy import AuditAction, authorize_audit_action

        authorize_audit_action(principal, AuditAction.READ)
        return await self.list(
            principal.organization_id,
            pagination=pagination,
            filters=filters,
        )

    async def list_for_case(
        self,
        principal: Principal,
        case_id: UUID,
        *,
        pagination: Pagination,
    ) -> Page[AuditEvent]:
        """Return a case's events under case-read access without tenant-wide browsing."""

        from app.services.auth.policy import CaseAction, authorize_case_action

        authorize_case_action(principal, CaseAction.READ)
        if await self.cases.get(principal.organization_id, case_id) is None:
            raise NotFoundError("Case")
        return await self.list(
            principal.organization_id,
            pagination=pagination,
            filters=AuditEventFilters(case_id=case_id),
        )
