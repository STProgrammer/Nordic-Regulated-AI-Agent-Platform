"""Shared PostgreSQL 16 + pgvector fixtures for database integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import AppSettings, reset_settings_cache
from app.db.models import Case, Document, Organization, Role, User, WorkflowRun
from app.db.session import dispose_database_engines, get_sessionmaker
from pydantic import SecretStr
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class TenantSeed:
    """Synthetic, committed records reused by Phase 5 integration assertions."""

    primary_organization_id: UUID
    isolated_organization_id: UUID
    primary_user_id: UUID
    isolated_user_id: UUID
    role_id: UUID
    primary_case_id: UUID
    isolated_case_id: UUID
    primary_document_id: UUID
    isolated_document_id: UUID
    primary_workflow_run_id: UUID
    isolated_workflow_run_id: UUID


def _async_url(sync_url: str) -> str:
    return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql+psycopg://", "postgresql+asyncpg://"
    )


def _alembic_config() -> Config:
    return Config(str(ROOT / "apps" / "api" / "alembic.ini"))


@pytest.fixture(scope="session")
def postgres_sync_url() -> Generator[str, None, None]:
    """Run integration tests against the same PostgreSQL + pgvector image as Compose."""

    try:
        postgres = PostgresContainer("pgvector/pgvector:0.8.0-pg16")
        postgres.start()
    except Exception as error:
        pytest.skip(f"PostgreSQL integration container is unavailable: {type(error).__name__}")
    try:
        yield postgres.get_connection_url()
    finally:
        postgres.stop()


@pytest.fixture
def database_settings(
    postgres_sync_url: str, monkeypatch: pytest.MonkeyPatch
) -> Generator[AppSettings, None, None]:
    """Reset a disposable integration database to Alembic head per test."""

    async_url = _async_url(postgres_sync_url)
    monkeypatch.setenv("NORDIC_API_DATABASE_URL", async_url)
    reset_settings_cache()
    command.downgrade(_alembic_config(), "base")
    command.upgrade(_alembic_config(), "head")
    settings = AppSettings(database_url=SecretStr(async_url))
    yield settings
    asyncio.run(dispose_database_engines())
    command.downgrade(_alembic_config(), "base")
    reset_settings_cache()


@pytest.fixture
def tenant_seed(database_settings: AppSettings) -> TenantSeed:
    """Create two strictly isolated synthetic tenants and core Phase 5 records."""

    return asyncio.run(_seed_tenants(database_settings))


async def _seed_tenants(settings: AppSettings) -> TenantSeed:
    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session, session.begin():
        primary_organization = Organization(
            name="Primary synthetic organization",
            slug="primary-synthetic",
            default_language="nb",
            retention_policy={},
            settings={},
        )
        isolated_organization = Organization(
            name="Isolated synthetic organization",
            slug="isolated-synthetic",
            default_language="nb",
            retention_policy={},
            settings={},
        )
        role = Role(name="Phase 5 Integration Role", description="Synthetic test role")
        session.add_all([primary_organization, isolated_organization, role])
        await session.flush()

        primary_user = User(
            organization_id=primary_organization.id,
            email="primary.user@demo.invalid",
            display_name="Primary Example",
            preferred_language="nb",
            is_active=True,
        )
        isolated_user = User(
            organization_id=isolated_organization.id,
            email="isolated.user@demo.invalid",
            display_name="Isolated Example",
            preferred_language="nb",
            is_active=True,
        )
        session.add_all([primary_user, isolated_user])
        await session.flush()

        primary_case = Case(
            organization_id=primary_organization.id,
            case_number="P5-PRIMARY",
            title="Primary synthetic case",
            description="Synthetic test record.",
            language="nb",
            domain="public_sector",
            priority="normal",
            status="new",
            submitted_by_user_id=primary_user.id,
        )
        isolated_case = Case(
            organization_id=isolated_organization.id,
            case_number="P5-ISOLATED",
            title="Isolated synthetic case",
            description="Synthetic test record.",
            language="nb",
            domain="public_sector",
            priority="normal",
            status="new",
            submitted_by_user_id=isolated_user.id,
        )
        session.add_all([primary_case, isolated_case])
        await session.flush()

        primary_document = _document(primary_organization.id, primary_case.id, primary_user.id, "P")
        isolated_document = _document(
            isolated_organization.id, isolated_case.id, isolated_user.id, "I"
        )
        session.add_all([primary_document, isolated_document])
        await session.flush()

        started_at = datetime.now(UTC)
        primary_workflow_run = WorkflowRun(
            organization_id=primary_organization.id,
            case_id=primary_case.id,
            started_by_user_id=primary_user.id,
            workflow_name="synthetic-workflow",
            workflow_version="1",
            status="queued",
            started_at=started_at,
            state_snapshot={},
        )
        isolated_workflow_run = WorkflowRun(
            organization_id=isolated_organization.id,
            case_id=isolated_case.id,
            started_by_user_id=isolated_user.id,
            workflow_name="synthetic-workflow",
            workflow_version="1",
            status="queued",
            started_at=started_at,
            state_snapshot={},
        )
        session.add_all([primary_workflow_run, isolated_workflow_run])
        await session.flush()

        seed = TenantSeed(
            primary_organization_id=primary_organization.id,
            isolated_organization_id=isolated_organization.id,
            primary_user_id=primary_user.id,
            isolated_user_id=isolated_user.id,
            role_id=role.id,
            primary_case_id=primary_case.id,
            isolated_case_id=isolated_case.id,
            primary_document_id=primary_document.id,
            isolated_document_id=isolated_document.id,
            primary_workflow_run_id=primary_workflow_run.id,
            isolated_workflow_run_id=isolated_workflow_run.id,
        )
    # The seed fixture runs in its own asyncio.run() loop. Dispose its pool
    # while that loop is alive so tests can construct a fresh pool per loop.
    await dispose_database_engines()
    return seed


def _document(organization_id: UUID, case_id: UUID, user_id: UUID, suffix: str) -> Document:
    return Document(
        organization_id=organization_id,
        case_id=case_id,
        uploaded_by_user_id=user_id,
        title=f"Synthetic document {suffix}",
        original_filename=f"synthetic-{suffix}.txt",
        file_type="txt",
        mime_type="text/plain",
        file_size_bytes=10,
        checksum_sha256=suffix.lower() * 64,
        object_storage_key=f"synthetic/{suffix}.txt",
        source_status="approved",
        confidentiality_level="internal",
        parsing_status="pending",
    )
