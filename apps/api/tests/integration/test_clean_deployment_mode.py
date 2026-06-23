"""Contracts for the migration-only clean deployment data baseline."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.core.config import AppSettings
from app.db.models import Approval
from app.db.session import dispose_database_engines, get_sessionmaker
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[4]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_clean_deployment_mode import (  # noqa: E402
    is_clean_deployment_mode,
    runtime_data_counts,
)
from scripts.seed_phase34_demo import seed_phase34_demo  # noqa: E402


def test_migration_only_database_is_clean_deployment_mode(database_settings: AppSettings) -> None:
    counts = runtime_data_counts(database_settings)

    assert is_clean_deployment_mode(counts)
    assert set(counts) == {
        "agent_messages",
        "approvals",
        "audit_events",
        "cases",
        "document_chunks",
        "document_texts",
        "documents",
        "eval_cases",
        "eval_datasets",
        "eval_results",
        "eval_runs",
        "extracted_fields",
        "memory_entries",
        "memory_usage_records",
        "model_usage_records",
        "organizations",
        "prompt_versions",
        "retrieved_sources",
        "risk_assessments",
        "roles",
        "user_roles",
        "users",
        "workflow_node_runs",
        "workflow_runs",
        "workflow_tool_calls",
    }
    assert set(counts.values()) == {0}


def test_explicit_phase34_demo_seed_is_not_clean_deployment_mode(
    database_settings: AppSettings,
) -> None:
    asyncio.run(_assert_explicit_demo_is_not_clean(database_settings))


async def _assert_explicit_demo_is_not_clean(settings: AppSettings) -> None:
    try:
        fixture = await seed_phase34_demo(
            settings,
            local_password="Synthetic demo password 42",  # pragma: allowlist secret
        )
        counts = runtime_data_counts(settings)

        assert not is_clean_deployment_mode(counts)
        assert counts["organizations"] == 1
        assert counts["users"] == 5
        assert counts["cases"] == 1
        assert counts["documents"] == 1
        assert counts["workflow_runs"] == 6
        assert counts["approvals"] == 1
        assert counts["audit_events"] >= 2
        assert counts["eval_runs"] == 1

        async with get_sessionmaker(settings)() as session:
            approval = await session.scalar(
                select(Approval).where(Approval.id == fixture["approval_id"])
            )
            assert approval is not None
            await session.delete(approval)
            await session.commit()
    finally:
        await dispose_database_engines()
