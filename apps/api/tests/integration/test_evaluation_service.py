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

            run_id = run.evaluation_run_id
            assert await service.execute(run_id) == "completed"
            assert await service.execute(run_id) == "noop"
            record = await service.get_run(primary, run_id)
            assert record.status == "completed"
            assert record.pass_fail == "pass"
            assert record.dataset_content_hash
            assert len(record.results) == 4
            assert all(item.passed for item in record.results)
            assert {item.case_key for item in record.results} == {
                "banking_review_en",
                "energy_weak_evidence_nb",
                "internal_sensitive_route_en",
                "public_policy_guidance_nb",
            }
            assert record.metrics.average_latency_ms is None
            assert record.metrics.total_cost_estimate is None
            result = await service.get_result(
                primary, run_id, record.results[0].evaluation_result_id
            )
            assert result.case_key == "banking_review_en"
            report = await service.export_report(primary, run_id, locale="en")
            assert report.startswith("# Evaluation report")
            assert "query" not in report
            assert await session.scalar(select(func.count()).select_from(EvalResult)) == 4

            with pytest.raises(NotFoundError):
                await service.get_run(isolated, run_id)
            with pytest.raises(NotFoundError):
                await service.get_result(isolated, run_id, result.evaluation_result_id)
            assert (await service.list_runs(isolated, pagination=_pagination())).total == 0

            event = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.organization_id == primary.organization_id,
                    AuditEvent.resource_id == run_id,
                    AuditEvent.event_type == "evaluation.report_exported",
                )
            )
            assert event is not None
            assert event.event_data == {
                "dataset_key": "nordic-regulated-core-v1",
                "dataset_version": "v1",
                "format": "markdown",
            }
            assert all(
                key not in event.event_data for key in {"query", "excerpt", "score", "exception"}
            )
            persisted = await session.get(EvalRun, run_id)
            assert persisted is not None and persisted.status == "completed"
    finally:
        await dispose_database_engines()


def _pagination() -> Pagination:
    return Pagination(limit=25, offset=0)
