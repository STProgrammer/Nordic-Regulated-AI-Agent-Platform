"""PostgreSQL integration tests for core repository tenant and archive behavior."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

import pytest
from app.core.config import AppSettings
from app.db.repositories.case import CaseRepository, CaseUpdateValues
from app.db.repositories.document import DocumentRepository
from app.db.repositories.identity import UserRepository
from app.db.repositories.workflow import WorkflowRunRepository
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.common.pagination import Pagination
from app.services.common.querying import SortDirection, SortSpec
from app.services.errors import InvalidQueryError


class TenantSeed(Protocol):
    primary_organization_id: UUID
    isolated_organization_id: UUID
    primary_user_id: UUID
    isolated_user_id: UUID
    primary_case_id: UUID
    primary_document_id: UUID
    primary_workflow_run_id: UUID


def test_core_repositories_enforce_tenant_scope_and_archive_defaults(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_run_core_repositories(database_settings, tenant_seed))


async def _run_core_repositories(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    try:
        await _exercise_core_repositories(settings, tenant_seed)
    finally:
        await dispose_database_engines()


async def _exercise_core_repositories(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    primary_organization_id = tenant_seed.primary_organization_id
    isolated_organization_id = tenant_seed.isolated_organization_id
    primary_user_id = tenant_seed.primary_user_id
    isolated_user_id = tenant_seed.isolated_user_id
    primary_case_id = tenant_seed.primary_case_id
    primary_document_id = tenant_seed.primary_document_id
    primary_workflow_run_id = tenant_seed.primary_workflow_run_id

    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        users = UserRepository(session)
        cases = CaseRepository(session)
        documents = DocumentRepository(session)
        workflows = WorkflowRunRepository(session)

        assert await users.get(primary_organization_id, primary_user_id) is not None
        assert await users.get(primary_organization_id, isolated_user_id) is None
        assert (
            await users.list(primary_organization_id, pagination=Pagination(limit=10))
        ).total == 1

        primary_case = await cases.get(primary_organization_id, primary_case_id)
        assert primary_case is not None
        assert await cases.get(isolated_organization_id, primary_case_id) is None
        assert (await cases.archive(isolated_organization_id, primary_case_id)) is None
        updated_case = await cases.update(
            primary_case, CaseUpdateValues(title="Updated synthetic case")
        )
        await session.flush()
        assert updated_case.title == "Updated synthetic case"

        case_page = await cases.list(
            primary_organization_id,
            pagination=Pagination(limit=1),
            sort=SortSpec("case_number", SortDirection.ASC),
        )
        assert case_page.total == 1
        assert case_page.items == (primary_case,)
        with pytest.raises(InvalidQueryError):
            await cases.list(
                primary_organization_id,
                pagination=Pagination(limit=1),
                sort=SortSpec("untrusted_sql_fragment"),
            )

        assert await documents.get(primary_organization_id, primary_document_id) is not None
        assert await documents.get(isolated_organization_id, primary_document_id) is None
        assert (await workflows.get(isolated_organization_id, primary_workflow_run_id)) is None
        assert (
            await workflows.list(isolated_organization_id, pagination=Pagination(limit=10))
        ).total == 1

        archived_case = await cases.archive(primary_organization_id, primary_case_id)
        archived_document = await documents.archive(primary_organization_id, primary_document_id)
        assert archived_case is not None
        assert archived_document is not None
        await session.flush()
        assert await cases.get(primary_organization_id, primary_case_id) is None
        assert await documents.get(primary_organization_id, primary_document_id) is None
        assert (
            await cases.get(primary_organization_id, primary_case_id, include_archived=True)
            is not None
        )
        assert (
            await documents.get(primary_organization_id, primary_document_id, include_archived=True)
        ) is not None
        assert (
            await cases.list(primary_organization_id, pagination=Pagination(limit=10))
        ).total == 0
        assert (
            await cases.list(
                primary_organization_id,
                pagination=Pagination(limit=10),
                include_archived=True,
            )
        ).total == 1
