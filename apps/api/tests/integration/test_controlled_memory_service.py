"""Durable controlled-memory service coverage using the Postgres LangGraph store."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

from agent_orchestrator.graphs.drafting_types import OutputLanguage
from agent_orchestrator.memory.policy import MemoryType
from agent_orchestrator.memory.store import PostgresControlledMemoryStore
from agent_orchestrator.types import WorkflowContext
from app.core.config import AppSettings
from app.db.models.memory import MemoryUsageRecord
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.auth.principal import Principal, RoleName
from app.services.memory.service import ControlledMemoryService, MemoryEntryCreate
from sqlalchemy import select


class TenantSeed(Protocol):
    primary_case_id: UUID
    primary_organization_id: UUID
    primary_user_id: UUID
    primary_workflow_run_id: UUID
    isolated_case_id: UUID
    isolated_organization_id: UUID
    isolated_user_id: UUID
    isolated_workflow_run_id: UUID


def test_controlled_memory_is_durable_scoped_and_disabled_fail_closed(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_run(database_settings, tenant_seed))


async def _run(settings: AppSettings, tenant_seed: TenantSeed) -> None:
    try:
        store = PostgresControlledMemoryStore(settings.langgraph_store_url())
        principal = Principal(
            user_id=tenant_seed.primary_user_id,
            organization_id=tenant_seed.primary_organization_id,
            display_name="Primary Example",
            preferred_language="nb",
            roles=frozenset({RoleName.ADMIN}),
        )
        sessionmaker = get_sessionmaker(settings)
        async with sessionmaker() as session:
            service = ControlledMemoryService(session, store=store)
            assert await service.enabled_for_organization(principal.organization_id) is False
            await service.set_enabled(principal, enabled=True)
            created = await service.create_organization_entry(
                principal,
                MemoryEntryCreate(
                    memory_type=MemoryType.APPROVED_TERMINOLOGY,
                    content={
                        "locale": "nb",
                        "source_term": "vedtak",
                        "preferred_term": "avgjørelse",
                    },
                ),
            )
            await session.commit()

        primary_context = WorkflowContext(
            workflow_run_id=tenant_seed.primary_workflow_run_id,
            organization_id=tenant_seed.primary_organization_id,
            case_id=tenant_seed.primary_case_id,
            initiated_by_user_id=tenant_seed.primary_user_id,
            workflow_name="drafting",
            workflow_version="test",
        )
        async with sessionmaker() as session:
            restarted_service = ControlledMemoryService(session, store=store)
            result = await restarted_service.presentation_context_for_drafting(
                primary_context,
                requested_language=OutputLanguage.NB,
                explicit_language=True,
            )
            assert result.memory_enabled is True
            assert result.presentation.terminology == (("vedtak", "avgjørelse"),)
            assert result.applied_count == 1
            usage = tuple((await session.scalars(select(MemoryUsageRecord))).all())
            assert usage and usage[0].memory_entry_id == created.id
            assert "vedtak" not in str(usage[0].__dict__)
            await session.commit()

        isolated_context = WorkflowContext(
            workflow_run_id=tenant_seed.isolated_workflow_run_id,
            organization_id=tenant_seed.isolated_organization_id,
            case_id=tenant_seed.isolated_case_id,
            initiated_by_user_id=tenant_seed.isolated_user_id,
            workflow_name="drafting",
            workflow_version="test",
        )
        async with sessionmaker() as session:
            isolated_principal = Principal(
                user_id=tenant_seed.isolated_user_id,
                organization_id=tenant_seed.isolated_organization_id,
                display_name="Isolated Example",
                preferred_language="nb",
                roles=frozenset({RoleName.ADMIN}),
            )
            isolated_service = ControlledMemoryService(session, store=store)
            await isolated_service.set_enabled(isolated_principal, enabled=True)
            await session.commit()
            isolated = await isolated_service.presentation_context_for_drafting(
                isolated_context,
                requested_language=OutputLanguage.NB,
                explicit_language=True,
            )
            assert isolated.memory_enabled is True
            assert isolated.presentation.terminology == ()
    finally:
        await dispose_database_engines()
