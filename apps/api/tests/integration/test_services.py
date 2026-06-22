"""PostgreSQL integration coverage for service validation and savepoint behavior."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Protocol
from uuid import UUID

import pytest
from app.core.config import AppSettings
from app.db.models import AuditEvent, Case
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.auth.principal import Principal, RoleName
from app.services.cases.service import CaseCreate, CasePatch, CaseService
from app.services.documents.service import DocumentService, DocumentUpload
from app.services.errors import ConflictError, InvalidCommandError, NotFoundError
from app.services.identity.service import IdentityService
from app.services.workflows.service import WorkflowRunService
from sqlalchemy import func, select


class TenantSeed(Protocol):
    primary_organization_id: UUID
    isolated_organization_id: UUID
    primary_user_id: UUID
    isolated_user_id: UUID
    role_id: UUID
    primary_workflow_run_id: UUID
    isolated_case_id: UUID


class _StorageFake:
    async def put_bytes(self, *, key: str, payload: bytes, content_type: str) -> None:
        return None

    async def delete(self, *, key: str) -> None:
        return None

    async def get_bytes(self, *, key: str, maximum_bytes: int) -> bytes:
        del key, maximum_bytes
        return b""


def test_services_scope_references_and_leave_session_usable_after_conflict(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_run_services(database_settings, tenant_seed))


async def _run_services(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    try:
        await _exercise_services(settings, tenant_seed)
    finally:
        await dispose_database_engines()


async def _exercise_services(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    primary_organization_id = tenant_seed.primary_organization_id
    isolated_organization_id = tenant_seed.isolated_organization_id
    primary_user_id = tenant_seed.primary_user_id
    isolated_user_id = tenant_seed.isolated_user_id
    role_id = tenant_seed.role_id
    primary_workflow_run_id = tenant_seed.primary_workflow_run_id
    isolated_case_id = tenant_seed.isolated_case_id

    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        cases = CaseService(session, case_number_factory=lambda: "P5-PRIMARY")
        documents = DocumentService(session, storage=_StorageFake(), maximum_upload_bytes=1024)
        identities = IdentityService(session)
        workflows = WorkflowRunService(session)

        with pytest.raises(ConflictError) as error:
            await cases.submit(
                Principal(
                    user_id=primary_user_id,
                    organization_id=primary_organization_id,
                    display_name="Primary Example",
                    preferred_language="nb",
                    roles=frozenset({RoleName.CASE_WORKER}),
                ),
                CaseCreate(
                    title="Duplicate synthetic case",
                    description="Synthetic conflict check.",
                    language="nb",
                    domain="public_sector",
                    priority="normal",
                ),
            )
        assert error.value.as_dict() == {
            "code": "conflict",
            "message": "Case conflicts with existing data.",
        }
        assert await session.scalar(select(func.count()).select_from(Case)) == 2

        with pytest.raises(NotFoundError):
            await documents.upload(
                Principal(
                    user_id=primary_user_id,
                    organization_id=primary_organization_id,
                    display_name="Primary Example",
                    preferred_language="nb",
                    roles=frozenset({RoleName.CASE_WORKER}),
                ),
                DocumentUpload(
                    case_id=isolated_case_id,
                    email_text="Synthetic email body.",
                ),
            )
        with pytest.raises(NotFoundError):
            await workflows.get_required(isolated_organization_id, primary_workflow_run_id)
        with pytest.raises(NotFoundError):
            await identities.assign_role(primary_organization_id, isolated_user_id, role_id)

        assignment = await identities.assign_role(primary_organization_id, primary_user_id, role_id)
        assert assignment.organization_id == primary_organization_id
        assert (
            len(
                await identities.assignments.list_for_user(primary_organization_id, primary_user_id)
            )
            == 1
        )


def test_case_service_writes_audit_events_with_successful_lifecycle_changes(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_run_case_lifecycle(database_settings, tenant_seed))


async def _run_case_lifecycle(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    try:
        await _exercise_case_lifecycle(settings, tenant_seed)
    finally:
        await dispose_database_engines()


async def _exercise_case_lifecycle(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    sessionmaker = get_sessionmaker(settings)
    principal = Principal(
        user_id=tenant_seed.primary_user_id,
        organization_id=tenant_seed.primary_organization_id,
        display_name="Primary Example",
        preferred_language="nb",
        roles=frozenset({RoleName.CASE_WORKER}),
    )
    async with sessionmaker() as session:
        cases = CaseService(session, today_provider=lambda: date(2030, 1, 1))
        created = await cases.submit(
            principal,
            CaseCreate(
                title="Synthetic lifecycle case",
                description="Synthetic lifecycle test content.",
                language="nb",
                domain="public_sector",
                priority="normal",
                due_date=date(2030, 1, 2),
            ),
        )
        assert created.case_number.startswith("CASE-")
        assert created.status == "new"

        with pytest.raises(InvalidCommandError):
            await cases.patch(principal, created.id, CasePatch(status="approved"))
        event_count = await session.scalar(select(func.count()).select_from(AuditEvent))
        assert event_count == 1

        updated = await cases.patch(principal, created.id, CasePatch(status="processing"))
        assert updated.status == "processing"
        archived = await cases.archive(principal, created.id)
        assert archived.status == "archived"
        assert archived.archived_at is not None
        assert await cases.repository.get(principal.organization_id, created.id) is None

        events = tuple(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.case_id == created.id)
                    .order_by(AuditEvent.inserted_at.asc())
                )
            ).all()
        )
        assert [event.event_type for event in events] == [
            "case.created",
            "case.status_changed",
            "case.archived",
        ]
        assert all("description" not in event.event_data for event in events)
