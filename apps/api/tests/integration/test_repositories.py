"""PostgreSQL integration tests for core repository tenant and archive behavior."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Protocol
from uuid import UUID

import pytest
from app.core.config import AppSettings
from app.db.models import Case
from app.db.repositories.case import CaseFilters, CaseRepository, CaseUpdateValues
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
        await cases.update(
            primary_case,
            CaseUpdateValues(
                assigned_user_id=primary_user_id,
                due_date=date(2030, 1, 1),
                external_reference="SYN-REFERENCE",
            ),
        )
        await cases.update(
            primary_case,
            CaseUpdateValues(assigned_user_id=None, due_date=None, external_reference=None),
        )
        await session.flush()
        assert updated_case.title == "Updated synthetic case"
        assert updated_case.assigned_user_id is None
        assert updated_case.due_date is None
        assert updated_case.external_reference is None

        case_page = await cases.list(
            primary_organization_id,
            pagination=Pagination(limit=1),
            sort=SortSpec("case_number", SortDirection.ASC),
        )
        assert case_page.total == 1
        assert case_page.items == (primary_case,)

        matching_primary = Case(
            organization_id=primary_organization_id,
            case_number="CASE-MATCHING-PRIMARY",
            title="Matched public-sector case",
            description="Need a synthetic matched record.",
            language="nb",
            domain="public_sector",
            priority="normal",
            status="processing",
            assigned_user_id=primary_user_id,
            submitted_by_user_id=primary_user_id,
        )
        matching_isolated = Case(
            organization_id=isolated_organization_id,
            case_number="CASE-MATCHING-ISOLATED",
            title="Matched isolated case",
            description="Must never leak into primary search.",
            language="nb",
            domain="public_sector",
            priority="normal",
            status="processing",
            assigned_user_id=isolated_user_id,
            submitted_by_user_id=isolated_user_id,
        )
        session.add_all([matching_primary, matching_isolated])
        await session.flush()
        filtered_page = await cases.list(
            primary_organization_id,
            pagination=Pagination(limit=10),
            filters=CaseFilters(
                status="processing",
                domain="public_sector",
                search_text="matched",
            ),
            sort=SortSpec("case_number", SortDirection.ASC),
        )
        assert filtered_page.total == 1
        assert filtered_page.items == (matching_primary,)
        assert await cases.list_assignee_options(primary_organization_id) == (
            (primary_user_id, "Primary Example"),
        )
        assert await cases.list_assignee_options(isolated_organization_id) == (
            (isolated_user_id, "Isolated Example"),
        )
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
        assert archived_case.status == "archived"
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
        ).total == 1
        assert (
            await cases.list(
                primary_organization_id,
                pagination=Pagination(limit=10),
                include_archived=True,
            )
        ).total == 2
