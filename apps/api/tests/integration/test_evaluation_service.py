"""Durable canonical evaluation loading, execution, and tenant isolation."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

import pytest
from app.core.config import AppSettings
from app.db.models import AuditEvent, EvalDataset, EvalResult, EvalRun
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.auth.principal import Principal, RoleName
from app.services.common.pagination import Pagination
from app.services.errors import ConflictError, NotFoundError
from app.services.evaluation.service import EvaluationService
from sqlalchemy import func, select


class TenantSeed(Protocol):
    primary_organization_id: UUID
    isolated_organization_id: UUID
    primary_user_id: UUID
    isolated_user_id: UUID


def test_evaluation_service_is_idempotent_tenant_scoped_and_safe(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_run(database_settings, tenant_seed))


async def _run(settings: AppSettings, seed: TenantSeed) -> None:
    primary = Principal(
        user_id=seed.primary_user_id,
        organization_id=seed.primary_organization_id,
        display_name="Primary administrator",
        preferred_language="nb",
        roles=frozenset({RoleName.ADMIN}),
    )
    isolated = Principal(
        user_id=seed.isolated_user_id,
        organization_id=seed.isolated_organization_id,
        display_name="Isolated administrator",
        preferred_language="en",
        roles=frozenset({RoleName.ADMIN}),
    )
    try:
        async with get_sessionmaker(settings)() as session:
            service = EvaluationService(session)
            datasets = await service.list_canonical_datasets(primary)
            assert len(datasets) == 1
            assert datasets[0].dataset.dataset_key == "nordic-regulated-core-v1"
            assert await session.scalar(select(func.count()).select_from(EvalDataset)) == 1

            run = await service.start(primary, dataset_key="nordic-regulated-core-v1")
            with pytest.raises(ConflictError):
                await service.start(primary, dataset_key="nordic-regulated-core-v1")

            assert await service.execute(run.id) == "completed"
            assert await service.execute(run.id) == "noop"
            record = await service.get_run(primary, run.id)
            assert record.run.status == "completed"
            assert record.run.pass_fail == "pass"
            assert record.run.dataset_content_hash
            assert len(record.results) == 4
            assert all(item.passed for item in record.results)
            assert set(record.result_case_keys.values()) == {
                "banking_review_en",
                "energy_weak_evidence_nb",
                "internal_sensitive_route_en",
                "public_policy_guidance_nb",
            }
            assert all("query" not in str(item.failure_reasons) for item in record.results)
            assert await session.scalar(select(func.count()).select_from(EvalResult)) == 4

            with pytest.raises(NotFoundError):
                await service.get_run(isolated, run.id)
            assert (await service.list_runs(isolated, pagination=_pagination())).total == 0

            event = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.organization_id == primary.organization_id,
                    AuditEvent.resource_id == run.id,
                    AuditEvent.event_type == "evaluation.run_completed",
                )
            )
            assert event is not None
            assert all(
                key not in event.event_data for key in {"query", "excerpt", "score", "exception"}
            )
            persisted = await session.get(EvalRun, run.id)
            assert persisted is not None and persisted.status == "completed"
    finally:
        await dispose_database_engines()


def _pagination() -> Pagination:
    return Pagination(limit=25, offset=0)
