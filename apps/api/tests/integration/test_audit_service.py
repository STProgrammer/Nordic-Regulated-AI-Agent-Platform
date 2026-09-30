"""PostgreSQL integration tests for explicit append-only tenant-scoped audit events."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

import pytest
from app.core.config import AppSettings
from app.db.repositories.audit import AuditEventFilters
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.audit.service import AuditEventInput, AuditService
from app.services.common.pagination import Pagination
from app.services.errors import InvalidCommandError, NotFoundError


class TenantSeed(Protocol):
    primary_organization_id: UUID
    isolated_organization_id: UUID
    primary_user_id: UUID
    primary_case_id: UUID


def test_audit_events_are_append_only_scoped_and_json_safe(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_run_audit_service(database_settings, tenant_seed))


async def _run_audit_service(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    try:
        await _exercise_audit_service(settings, tenant_seed)
    finally:
        await dispose_database_engines()


async def _exercise_audit_service(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    primary_organization_id = tenant_seed.primary_organization_id
    isolated_organization_id = tenant_seed.isolated_organization_id
    primary_user_id = tenant_seed.primary_user_id
    primary_case_id = tenant_seed.primary_case_id

    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        service = AuditService(session)
        event = await service.record_event(
            AuditEventInput(
                organization_id=primary_organization_id,
                actor_user_id=primary_user_id,
                case_id=primary_case_id,
                event_type="synthetic.case.checked",
                resource_type="case",
                resource_id=primary_case_id,
                event_data={"result": "safe", "checks": ["tenant", "audit"]},
            )
        )
        assert event.event_data == {"result": "safe", "checks": ["tenant", "audit"]}
        read_count_before = (
            await service.list(primary_organization_id, pagination=Pagination(limit=10))
        ).total
        assert read_count_before == 1
        assert await service.get_required(primary_organization_id, event.id) is event
        with pytest.raises(NotFoundError):
            await service.get_required(isolated_organization_id, event.id)
        assert (
            await service.list(isolated_organization_id, pagination=Pagination(limit=10))
        ).total == 0
        assert (
            await service.list(
                primary_organization_id,
                pagination=Pagination(limit=10),
                filters=AuditEventFilters(event_type="synthetic.case.checked"),
            )
        ).total == 1
        assert (
            await service.list(primary_organization_id, pagination=Pagination(limit=10))
        ).total == read_count_before
        assert not hasattr(service.repository, "update")
        assert not hasattr(service.repository, "delete")
        assert not hasattr(service.repository, "archive")

        with pytest.raises(InvalidCommandError):
            await service.record_event(
                AuditEventInput(
                    organization_id=primary_organization_id,
                    event_type="synthetic.unsafe",
                    resource_type="case",
                    event_data={"token": "not allowed"},
                )
            )
