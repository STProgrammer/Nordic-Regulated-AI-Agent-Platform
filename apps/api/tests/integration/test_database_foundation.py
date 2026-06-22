"""PostgreSQL + pgvector integration coverage for the Phase 4 schema baseline."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import AppSettings
from app.core.security import PasswordSecurity
from app.db.base import EMBEDDING_DIMENSIONS
from app.db.models import (
    AgentMessage,
    Approval,
    AuditEvent,
    Case,
    Document,
    DocumentChunk,
    DocumentText,
    EvalCase,
    EvalDataset,
    EvalResult,
    EvalRun,
    ExtractedField,
    MemoryEntry,
    ModelUsageRecord,
    Organization,
    PromptVersion,
    RetrievedSource,
    RiskAssessment,
    Role,
    User,
    UserRole,
    WorkflowNodeRun,
    WorkflowRun,
)
from app.db.seed import ROLE_DESCRIPTIONS, SEED_USERS, seed_local
from app.db.session import get_sessionmaker
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[4]
EXPECTED_TABLES = {
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
    "workflow_tool_calls",
    "workflow_runs",
}


def _alembic_config() -> Config:
    return Config(str(ROOT / "apps" / "api" / "alembic.ini"))


def test_baseline_migration_creates_postgresql_contract(
    database_settings: AppSettings,
) -> None:
    """The baseline must include every table, extension, and retrieval index."""

    engine = create_engine(database_settings.database_sync_url())
    try:
        assert EXPECTED_TABLES.issubset(inspect(engine).get_table_names())
        with engine.connect() as connection:
            extensions = set(
                connection.execute(
                    text("SELECT extname FROM pg_extension WHERE extname IN ('pgcrypto', 'vector')")
                ).scalars()
            )
            assert extensions == {"pgcrypto", "vector"}
        case_constraints = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspect(engine).get_check_constraints("cases")
        }
        assert "ck_cases_domain_allowed" in case_constraints
        assert "public_sector" in case_constraints["ck_cases_domain_allowed"]
        assert "internal_policy" in case_constraints["ck_cases_domain_allowed"]
        with engine.connect() as connection:
            dimension = connection.execute(
                text(
                    """
                    SELECT format_type(attribute.atttypid, attribute.atttypmod)
                    FROM pg_attribute AS attribute
                    WHERE attribute.attrelid = 'document_chunks'::regclass
                      AND attribute.attname = 'embedding'
                    """
                )
            ).scalar_one()
            assert dimension == f"vector({EMBEDDING_DIMENSIONS})"
            indexes = {
                row[0]: row[1]
                for row in connection.execute(
                    text(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE tablename = 'document_chunks'
                        """
                    )
                )
            }
            assert "vector_cosine_ops" in indexes["ix_document_chunks_embedding_hnsw"]
            assert "USING hnsw" in indexes["ix_document_chunks_embedding_hnsw"]
            assert (
                "to_tsvector('simple'::regconfig, content)"
                in indexes["ix_document_chunks_content_fts"]
            )
            connection.execute(text("SET LOCAL enable_seqscan = off"))
            full_text_plan = "\n".join(
                connection.execute(
                    text(
                        """
                        EXPLAIN (COSTS OFF)
                        SELECT id
                        FROM document_chunks
                        WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', 'norsk')
                        """
                    )
                ).scalars()
            )
            vector_literal = "[" + ",".join("0" for _ in range(EMBEDDING_DIMENSIONS)) + "]"
            vector_plan = "\n".join(
                connection.execute(
                    text(
                        """
                        EXPLAIN (COSTS OFF)
                        SELECT id
                        FROM document_chunks
                        ORDER BY embedding <=> CAST(:embedding AS vector)
                        LIMIT 1
                        """
                    ),
                    {"embedding": vector_literal},
                ).scalars()
            )
            assert "ix_document_chunks_content_fts" in full_text_plan
            assert "ix_document_chunks_embedding_hnsw" in vector_plan
    finally:
        engine.dispose()


def test_case_domain_migration_repairs_legacy_synthetic_rows(
    database_settings: AppSettings,
) -> None:
    """An old unconstrained fixture must not make the Case Inbox unavailable after upgrade."""

    organization_id = uuid4()
    user_id = uuid4()
    case_id = uuid4()
    config = _alembic_config()
    command.downgrade(config, "e25a1c6d7f90")

    engine = create_engine(database_settings.database_sync_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, default_language) "
                    "VALUES (:id, 'Legacy domain tenant', 'legacy-domain-tenant', 'nb')"
                ),
                {"id": organization_id},
            )
            connection.execute(
                text(
                    "INSERT INTO users ("
                    "id, organization_id, email, display_name, preferred_language"
                    ") "
                    "VALUES (:id, :organization_id, 'legacy.domain@demo.invalid', "
                    "'Legacy Domain User', 'nb')"
                ),
                {"id": user_id, "organization_id": organization_id},
            )
            connection.execute(
                text(
                    "INSERT INTO cases ("
                    "id, organization_id, case_number, title, description, language, domain, "
                    "priority, status, submitted_by_user_id"
                    ") VALUES ("
                    ":id, :organization_id, 'LEGACY-DOMAIN-1', 'Legacy domain case', "
                    "'Synthetic migration record.', 'nb', 'testing', 'normal', 'new', :user_id"
                    ")"
                ),
                {"id": case_id, "organization_id": organization_id, "user_id": user_id},
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            repaired_domain = connection.execute(
                text("SELECT domain FROM cases WHERE id = :id"), {"id": case_id}
            ).scalar_one()
        assert repaired_domain == "internal_policy"
    finally:
        engine.dispose()


def test_human_approval_migration_normalizes_legacy_decisions(
    database_settings: AppSettings,
) -> None:
    """Upgrade legacy placeholder rows without violating the closed Phase 22 decision domain."""

    config = _alembic_config()
    command.downgrade(config, "7a21c9e5b406")
    organization_id, user_id, case_id = uuid4(), uuid4(), uuid4()
    approved_run_id, unknown_run_id = uuid4(), uuid4()
    approved_id, unknown_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    engine = create_engine(database_settings.database_sync_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO organizations (id, name, slug, default_language)
                    VALUES (:id, 'Legacy approval tenant', 'legacy-approval-tenant', 'nb')
                    """
                ),
                {"id": organization_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, organization_id, email, display_name, preferred_language)
                    VALUES (:id, :organization_id, 'legacy.approver@demo.invalid',
                            'Legacy Approver', 'nb')
                    """
                ),
                {"id": user_id, "organization_id": organization_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO cases (
                        id, organization_id, case_number, title, description, language, domain,
                        priority, status, submitted_by_user_id
                    )
                    VALUES (
                        :id, :organization_id, 'LEGACY-APPROVAL-1', 'Legacy approval case',
                        'Synthetic migration record.', 'nb', 'internal_policy', 'normal', 'new',
                        :user_id
                    )
                    """
                ),
                {"id": case_id, "organization_id": organization_id, "user_id": user_id},
            )
            for workflow_run_id in (approved_run_id, unknown_run_id):
                connection.execute(
                    text(
                        """
                        INSERT INTO workflow_runs (
                            id, organization_id, case_id, workflow_name, workflow_version, status,
                            started_by_user_id, started_at
                        )
                        VALUES (
                            :id, :organization_id, :case_id, 'legacy-approval', 'v1', 'completed',
                            :user_id, :started_at
                        )
                        """
                    ),
                    {
                        "id": workflow_run_id,
                        "organization_id": organization_id,
                        "case_id": case_id,
                        "user_id": user_id,
                        "started_at": now,
                    },
                )
            for approval_id, workflow_run_id, decision in (
                (approved_id, approved_run_id, "approved"),
                (unknown_id, unknown_run_id, "legacy-custom-decision"),
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO approvals (
                            id, organization_id, case_id, workflow_run_id, reviewer_user_id,
                            decision, decision_at
                        )
                        VALUES (
                            :id, :organization_id, :case_id, :workflow_run_id, :user_id, :decision,
                            :decision_at
                        )
                        """
                    ),
                    {
                        "id": approval_id,
                        "organization_id": organization_id,
                        "case_id": case_id,
                        "workflow_run_id": workflow_run_id,
                        "user_id": user_id,
                        "decision": decision,
                        "decision_at": now,
                    },
                )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_settings.database_sync_url())
    try:
        with engine.connect() as connection:
            rows: dict[UUID, str] = {
                cast(UUID, row["id"]): cast(str, row["lifecycle"])
                for row in connection.execute(
                    text(
                        """
                        SELECT id, status || ':' || decision AS lifecycle
                        FROM approvals
                        WHERE id IN (:approved_id, :unknown_id)
                        """
                    ).bindparams(approved_id=approved_id, unknown_id=unknown_id)
                ).mappings()
            }
        assert rows == {
            approved_id: "approved:approve",
            unknown_id: "needs_more_evidence:request_more_evidence",
        }
    finally:
        engine.dispose()


def test_representative_records_enforce_tenant_and_schema_invariants(
    database_settings: AppSettings,
) -> None:
    """Exercise representative storage for every entity and database constraints."""

    asyncio.run(_exercise_records(database_settings))


async def _exercise_records(settings: AppSettings) -> None:
    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        async with session.begin():
            now = datetime.now(UTC)
            organization = Organization(
                name="Synthetic primary organization",
                slug="synthetic-primary",
                default_language="nb",
                retention_policy={"days": 30},
                settings={"synthetic": True},
            )
            second_organization = Organization(
                name="Synthetic isolated organization",
                slug="synthetic-isolated",
                default_language="nb",
                retention_policy={},
                settings={},
            )
            role = Role(name="Integration Role", description="Synthetic integration role")
            session.add_all([organization, second_organization, role])
            await session.flush()

            user = User(
                organization_id=organization.id,
                email="integration.user@demo.invalid",
                display_name="Integration Eksempel",
                preferred_language="nb",
                is_active=True,
            )
            second_user = User(
                organization_id=second_organization.id,
                email="integration.isolated@demo.invalid",
                display_name="Isolert Eksempel",
                preferred_language="nb",
                is_active=True,
            )
            session.add_all([user, second_user])
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=role.id, organization_id=organization.id))

            case = Case(
                organization_id=organization.id,
                case_number="SYN-001",
                title="Syntetisk sak",
                description="Kun integrasjonstestdata.",
                language="nb",
                domain="public_sector",
                priority="normal",
                status="new",
                submitted_by_user_id=user.id,
            )
            isolated_case = Case(
                organization_id=second_organization.id,
                case_number="ISO-001",
                title="Isolert syntetisk sak",
                description="Kun integrasjonstestdata.",
                language="nb",
                domain="public_sector",
                priority="normal",
                status="new",
                submitted_by_user_id=second_user.id,
            )
            session.add_all([case, isolated_case])
            await session.flush()

            document = Document(
                organization_id=organization.id,
                case_id=case.id,
                uploaded_by_user_id=user.id,
                title="Syntetisk vedlegg",
                original_filename="syntetisk.txt",
                file_type="txt",
                mime_type="text/plain",
                file_size_bytes=42,
                checksum_sha256="a" * 64,
                object_storage_key="synthetic/integration.txt",
                source_status="approved",
                confidentiality_level="internal",
                parsing_status="pending",
            )
            session.add(document)
            await session.flush()
            chunk = DocumentChunk(
                organization_id=organization.id,
                document_id=document.id,
                chunk_index=0,
                content="Norsk og English retrieval content.",
                token_count=6,
                chunk_metadata={"page": 1},
                embedding=[0.0] * EMBEDDING_DIMENSIONS,
            )
            session.add_all(
                [
                    DocumentText(
                        document_id=document.id,
                        extracted_text="Norsk og English retrieval content.",
                        extraction_metadata={"synthetic": True},
                    ),
                    chunk,
                ]
            )
            await session.flush()

            prompt = PromptVersion(name="integration", version="1", content="Synthetic prompt")
            workflow = WorkflowRun(
                organization_id=organization.id,
                case_id=case.id,
                workflow_name="integration",
                workflow_version="1",
                status="completed",
                started_by_user_id=user.id,
                started_at=now,
                total_cost_estimate=Decimal("0.010000"),
                total_tokens=12,
                state_snapshot={"synthetic": True},
            )
            dataset = EvalDataset(
                name="synthetic dataset",
                description="Synthetic integration dataset",
                dataset_version="1",
                domain="testing",
            )
            session.add_all([prompt, workflow, dataset])
            await session.flush()
            eval_case = EvalCase(
                eval_dataset_id=dataset.id,
                input_case={"title": "synthetic"},
                expected_behavior={"refuse": False},
                expected_sources={"count": 1},
                tags=["synthetic", "nb"],
            )
            eval_run = EvalRun(
                eval_dataset_id=dataset.id,
                run_name="synthetic run",
                status="completed",
                started_at=now,
                summary_metrics={"pass_rate": "1"},
                pass_fail="pass",
            )
            session.add_all([eval_case, eval_run])
            await session.flush()
            session.add_all(
                [
                    WorkflowNodeRun(
                        workflow_run_id=workflow.id,
                        node_name="integration",
                        status="completed",
                        started_at=now,
                        input_summary={},
                        output_summary={},
                        retry_count=0,
                    ),
                    AgentMessage(
                        organization_id=organization.id,
                        case_id=case.id,
                        workflow_run_id=workflow.id,
                        message_type="draft",
                        role="assistant",
                        content="Syntetisk svar",
                        model_provider="test",
                        model_name="test-model",
                        prompt_version_id=prompt.id,
                        token_input=4,
                        token_output=8,
                        cost_estimate=Decimal("0.010000"),
                        latency_ms=3,
                    ),
                    RetrievedSource(
                        organization_id=organization.id,
                        case_id=case.id,
                        workflow_run_id=workflow.id,
                        document_id=document.id,
                        chunk_id=chunk.id,
                        rank=0,
                        score=Decimal("0.99000000"),
                        retrieval_method="synthetic",
                        excerpt="Syntetisk kilde",
                        citation_label="Vedlegg 1",
                    ),
                    ExtractedField(
                        organization_id=organization.id,
                        case_id=case.id,
                        workflow_run_id=workflow.id,
                        field_name="synthetic",
                        field_value={"value": "ok"},
                        confidence=Decimal("0.90000000"),
                        source_chunk_id=chunk.id,
                        human_edited=False,
                    ),
                    RiskAssessment(
                        organization_id=organization.id,
                        case_id=case.id,
                        workflow_run_id=workflow.id,
                        risk_level="low",
                        risk_reasons={"synthetic": True},
                        pii_detected=False,
                        prompt_injection_detected=False,
                        weak_evidence=False,
                        high_impact_action=False,
                        requires_approval=False,
                    ),
                    Approval(
                        organization_id=organization.id,
                        case_id=case.id,
                        workflow_run_id=workflow.id,
                        reviewer_user_id=user.id,
                        assigned_user_id=user.id,
                        status="approved",
                        decision="edit_and_approve",
                        decision_at=now,
                        ai_draft="Syntetisk utkast",
                        final_text="Syntetisk endelig tekst",
                    ),
                    AuditEvent(
                        organization_id=organization.id,
                        actor_user_id=user.id,
                        event_type="synthetic.created",
                        resource_type="case",
                        resource_id=case.id,
                        case_id=case.id,
                        ip_address="127.0.0.1",
                        event_data={"synthetic": True},
                    ),
                    ModelUsageRecord(
                        organization_id=organization.id,
                        case_id=case.id,
                        workflow_run_id=workflow.id,
                        provider="test",
                        model_name="test-model",
                        operation="draft",
                        token_input=4,
                        token_output=8,
                        cost_estimate=Decimal("0.010000"),
                        latency_ms=3,
                        success=True,
                    ),
                    EvalResult(
                        eval_run_id=eval_run.id,
                        eval_case_id=eval_case.id,
                        workflow_run_id=workflow.id,
                        retrieval_score=Decimal("0.90000000"),
                        citation_score=Decimal("0.90000000"),
                        faithfulness_score=Decimal("0.90000000"),
                        refusal_score=Decimal("1.00000000"),
                        latency_ms=3,
                        cost_estimate=Decimal("0.010000"),
                        passed=True,
                        failure_reasons={},
                    ),
                    MemoryEntry(
                        organization_id=organization.id,
                        user_id=user.id,
                        memory_scope="user",
                        memory_type="ui_language_preference",
                        content={"language": "nb"},
                        source="self_preference",
                        store_key="synthetic-memory-store-key",
                        natural_key="ui_language_preference",
                        is_active=True,
                    ),
                ]
            )
            await session.flush()
            assert organization.id is not None
            assert document.inserted_at.tzinfo is not None
            assert workflow.total_cost_estimate == Decimal("0.010000")
            assert await session.scalar(select(func.count()).select_from(EvalResult)) == 1

        async with session.begin():
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(
                        Case(
                            organization_id=organization.id,
                            case_number=case.case_number,
                            title="Duplicate case number",
                            description="Synthetic constraint test.",
                            language="nb",
                            domain="public_sector",
                            priority="normal",
                            status="new",
                            submitted_by_user_id=user.id,
                        )
                    )
                    await session.flush()
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(
                        Case(
                            organization_id=organization.id,
                            case_number="INVALID-DOMAIN",
                            title="Invalid domain case",
                            description="Synthetic constraint test.",
                            language="nb",
                            domain="testing",
                            priority="normal",
                            status="new",
                            submitted_by_user_id=user.id,
                        )
                    )
                    await session.flush()
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(
                        UserRole(
                            user_id=user.id,
                            role_id=role.id,
                            organization_id=organization.id,
                        )
                    )
                    await session.flush()
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(
                        DocumentChunk(
                            organization_id=organization.id,
                            document_id=document.id,
                            chunk_index=0,
                            content="Duplicate synthetic chunk.",
                            token_count=3,
                            chunk_metadata={},
                            embedding=[0.0] * EMBEDDING_DIMENSIONS,
                        )
                    )
                    await session.flush()
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(
                        Document(
                            organization_id=organization.id,
                            case_id=isolated_case.id,
                            uploaded_by_user_id=user.id,
                            title="Cross tenant reference",
                            original_filename="invalid.txt",
                            file_type="txt",
                            mime_type="text/plain",
                            file_size_bytes=1,
                            checksum_sha256="b" * 64,
                            object_storage_key="synthetic/invalid.txt",
                            source_status="approved",
                            confidentiality_level="internal",
                            parsing_status="pending",
                        )
                    )
                    await session.flush()


def test_seed_and_downgrade_reupgrade_are_safe_and_repeatable(
    database_settings: AppSettings,
) -> None:
    """Seed fixtures must be password-free and a clean rollback must replay."""

    asyncio.run(_seed_twice(database_settings))
    command.downgrade(_alembic_config(), "base")
    engine = create_engine(database_settings.database_sync_url())
    try:
        assert not (EXPECTED_TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()


def test_local_seed_password_requires_explicit_input_and_is_never_plaintext(
    database_settings: AppSettings,
) -> None:
    asyncio.run(_seed_with_local_password(database_settings))
    command.upgrade(_alembic_config(), "head")
    engine = create_engine(database_settings.database_sync_url())
    try:
        assert EXPECTED_TABLES.issubset(inspect(engine).get_table_names())
    finally:
        engine.dispose()


async def _seed_twice(settings: AppSettings) -> None:
    await seed_local(settings)
    await seed_local(settings)
    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        roles = set((await session.scalars(select(Role.name))).all())
        users = (
            await session.scalars(select(User).where(User.email.in_([u.email for u in SEED_USERS])))
        ).all()
        memberships = await session.scalar(select(func.count()).select_from(UserRole))
        assert set(ROLE_DESCRIPTIONS).issubset(roles)
        assert len(users) == len(SEED_USERS)
        assert all(user.password_hash is None for user in users)
        assert memberships == len(SEED_USERS)


async def _seed_with_local_password(settings: AppSettings) -> None:
    local_password = "Synthetic seed password 42"
    await seed_local(settings, local_password=local_password)
    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        users = (
            await session.scalars(
                select(User).where(User.email.in_([user.email for user in SEED_USERS]))
            )
        ).all()
    security = PasswordSecurity(
        minimum_length=settings.password_min_length,
        maximum_length=settings.password_max_length,
    )
    assert len(users) == len(SEED_USERS)
    assert all(user.password_hash is not None for user in users)
    assert all(user.password_hash != local_password for user in users)
    assert all(security.verify(local_password, user.password_hash or "").verified for user in users)
