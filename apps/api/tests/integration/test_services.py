"""PostgreSQL integration coverage for service validation and savepoint behavior."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

import pytest
from app.core.config import AppSettings
from app.db.models import Case
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.cases.service import CaseCreate, CaseService
from app.services.documents.service import DocumentCreate, DocumentService
from app.services.errors import ConflictError, NotFoundError
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
        cases = CaseService(session)
        documents = DocumentService(session)
        identities = IdentityService(session)
        workflows = WorkflowRunService(session)

        with pytest.raises(ConflictError) as error:
            await cases.create(
                CaseCreate(
                    organization_id=primary_organization_id,
                    case_number="P5-PRIMARY",
                    title="Duplicate synthetic case",
                    description="Synthetic conflict check.",
                    language="nb",
                    domain="testing",
                    priority="normal",
                    status="new",
                    submitted_by_user_id=primary_user_id,
                )
            )
        assert error.value.as_dict() == {
            "code": "conflict",
            "message": "Case conflicts with existing data.",
        }
        assert await session.scalar(select(func.count()).select_from(Case)) == 2

        with pytest.raises(NotFoundError):
            await documents.create(
                DocumentCreate(
                    organization_id=primary_organization_id,
                    uploaded_by_user_id=primary_user_id,
                    case_id=isolated_case_id,
                    title="Invalid cross-tenant document",
                    original_filename="invalid.txt",
                    file_type="txt",
                    mime_type="text/plain",
                    file_size_bytes=1,
                    checksum_sha256="e" * 64,
                    object_storage_key="synthetic/invalid.txt",
                    source_status="approved",
                    confidentiality_level="internal",
                    parsing_status="pending",
                )
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
