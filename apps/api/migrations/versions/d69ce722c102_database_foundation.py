"""database foundation

Revision ID: d69ce722c102
Revises:
Create Date: 2026-06-20 04:09:09.092033
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d69ce722c102"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These extensions are available on the supported local pgvector PostgreSQL
    # image. IF NOT EXISTS preserves an operator-managed installation.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE FUNCTION phase4_set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = timezone('utc', now());
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.create_table(
        "organizations",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("default_language", sa.String(length=16), nullable=False),
        sa.Column(
            "retention_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_table(
        "eval_datasets",
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dataset_version", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_eval_datasets_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_datasets")),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_prompt_versions_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_versions")),
    )
    op.create_table(
        "users",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("identity_provider", sa.String(length=100), nullable=True),
        sa.Column("identity_subject", sa.String(length=255), nullable=True),
        sa.Column("preferred_language", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_users_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("id", "organization_id", name="uq_users_id_organization"),
    )
    op.create_table(
        "cases",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_number", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False),
        sa.Column("case_type", sa.String(length=100), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=True),
        sa.Column("assigned_user_id", sa.UUID(), nullable=True),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "assigned_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_cases_organization_assigned_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "submitted_by_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_cases_organization_submitted_by_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_cases_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
        sa.UniqueConstraint("id", "organization_id", name="uq_cases_id_organization"),
        sa.UniqueConstraint(
            "organization_id", "case_number", name="uq_cases_organization_case_number"
        ),
    )
    op.create_index(
        "ix_cases_organization_case_number",
        "cases",
        ["organization_id", "case_number"],
        unique=False,
    )
    op.create_index(
        "ix_cases_organization_inserted_at",
        "cases",
        ["organization_id", "inserted_at"],
        unique=False,
    )
    op.create_index(
        "ix_cases_organization_risk_level", "cases", ["organization_id", "risk_level"], unique=False
    )
    op.create_index(
        "ix_cases_organization_status", "cases", ["organization_id", "status"], unique=False
    )
    op.create_table(
        "eval_cases",
        sa.Column("eval_dataset_id", sa.UUID(), nullable=False),
        sa.Column("input_case", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_behavior", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_risk_level", sa.String(length=50), nullable=True),
        sa.Column(
            "tags", sa.ARRAY(sa.String()), server_default=sa.text("'{}'::text[]"), nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["eval_dataset_id"],
            ["eval_datasets.id"],
            name=op.f("fk_eval_cases_eval_dataset_id_eval_datasets"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_cases")),
    )
    op.create_table(
        "eval_runs",
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("eval_dataset_id", sa.UUID(), nullable=False),
        sa.Column("run_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "summary_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("pass_fail", sa.String(length=50), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["eval_dataset_id"],
            ["eval_datasets.id"],
            name=op.f("fk_eval_runs_eval_dataset_id_eval_datasets"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_eval_runs_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_runs")),
    )
    op.create_table(
        "memory_entries",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("memory_scope", sa.String(length=100), nullable=False),
        sa.Column("memory_type", sa.String(length=100), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_memory_entries_organization_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_memory_entries_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_entries")),
        sa.UniqueConstraint("id", "organization_id", name="uq_memory_entries_id_organization"),
    )
    op.create_index(
        "ix_memory_entries_organization_memory_scope",
        "memory_entries",
        ["organization_id", "memory_scope"],
        unique=False,
    )
    op.create_index(
        "ix_memory_entries_organization_user",
        "memory_entries",
        ["organization_id", "user_id"],
        unique=False,
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_user_roles_organization_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_user_roles_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id_roles")
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "role_id", "organization_id", name=op.f("pk_user_roles")
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_audit_events_organization_actor_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_audit_events_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_audit_events_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"], unique=False)
    op.create_index(
        "ix_audit_events_organization_event_type",
        "audit_events",
        ["organization_id", "event_type"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_organization_inserted_at",
        "audit_events",
        ["organization_id", "inserted_at"],
        unique=False,
    )
    op.create_table(
        "documents",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("object_storage_key", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("source_status", sa.String(length=50), nullable=False),
        sa.Column("confidentiality_level", sa.String(length=50), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("parsing_status", sa.String(length=50), nullable=False),
        sa.Column("parsing_error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "file_size_bytes >= 0", name=op.f("ck_documents_file_size_bytes_nonnegative")
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count >= 0",
            name=op.f("ck_documents_page_count_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_documents_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "uploaded_by_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_documents_organization_uploaded_by_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_documents_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("id", "organization_id", name="uq_documents_id_organization"),
    )
    op.create_index("ix_documents_checksum_sha256", "documents", ["checksum_sha256"], unique=False)
    op.create_index(
        "ix_documents_organization_case", "documents", ["organization_id", "case_id"], unique=False
    )
    op.create_index(
        "ix_documents_organization_source_status",
        "documents",
        ["organization_id", "source_status"],
        unique=False,
    )
    op.create_table(
        "workflow_runs",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("workflow_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_by_user_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("total_cost_estimate", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "state_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name=op.f("ck_workflow_runs_duration_ms_nonnegative"),
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name=op.f("ck_workflow_runs_total_tokens_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_workflow_runs_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "started_by_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_workflow_runs_organization_started_by_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_workflow_runs_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_runs")),
        sa.UniqueConstraint("id", "organization_id", name="uq_workflow_runs_id_organization"),
    )
    op.create_index(
        "ix_workflow_runs_organization_case",
        "workflow_runs",
        ["organization_id", "case_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_runs_organization_status",
        "workflow_runs",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_runs_organization_workflow_name",
        "workflow_runs",
        ["organization_id", "workflow_name"],
        unique=False,
    )
    op.create_table(
        "agent_messages",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("message_type", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_provider", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("prompt_version_id", sa.UUID(), nullable=True),
        sa.Column("token_input", sa.Integer(), nullable=True),
        sa.Column("token_output", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name=op.f("ck_agent_messages_latency_ms_nonnegative"),
        ),
        sa.CheckConstraint(
            "token_input IS NULL OR token_input >= 0",
            name=op.f("ck_agent_messages_token_input_nonnegative"),
        ),
        sa.CheckConstraint(
            "token_output IS NULL OR token_output >= 0",
            name=op.f("ck_agent_messages_token_output_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_agent_messages_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_agent_messages_organization_workflow_run",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_agent_messages_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"],
            ["prompt_versions.id"],
            name=op.f("fk_agent_messages_prompt_version_id_prompt_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_messages")),
    )
    op.create_table(
        "approvals",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_user_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.Column("ai_draft", sa.Text(), nullable=True),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_approvals_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_approvals_organization_reviewer_user",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_approvals_organization_workflow_run",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_approvals_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
    )
    op.create_table(
        "document_chunks",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index >= 0", name=op.f("ck_document_chunks_chunk_index_nonnegative")
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 0",
            name=op.f("ck_document_chunks_page_number_nonnegative"),
        ),
        sa.CheckConstraint(
            "token_count >= 0", name=op.f("ck_document_chunks_token_count_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_document_chunks_organization_document",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_document_chunks_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_chunk_index"
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_document_chunks_id_organization"),
    )
    op.create_index(
        "ix_document_chunks_content_fts",
        "document_chunks",
        [sa.literal_column("to_tsvector('simple', content)")],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    op.create_index(
        "ix_document_chunks_organization_document",
        "document_chunks",
        ["organization_id", "document_id"],
        unique=False,
    )
    op.create_table(
        "document_texts",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column(
            "extraction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name=op.f("fk_document_texts_document_id_documents")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_texts")),
        sa.UniqueConstraint("document_id", name=op.f("uq_document_texts_document_id")),
    )
    op.create_table(
        "eval_results",
        sa.Column("eval_run_id", sa.UUID(), nullable=False),
        sa.Column("eval_case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=True),
        sa.Column("retrieval_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("citation_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("faithfulness_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("refusal_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column(
            "failure_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["eval_case_id"],
            ["eval_cases.id"],
            name=op.f("fk_eval_results_eval_case_id_eval_cases"),
        ),
        sa.ForeignKeyConstraint(
            ["eval_run_id"], ["eval_runs.id"], name=op.f("fk_eval_results_eval_run_id_eval_runs")
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_eval_results_workflow_run_id_workflow_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_results")),
    )
    op.create_table(
        "model_usage_records",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("workflow_run_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("token_input", sa.Integer(), nullable=True),
        sa.Column("token_output", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name=op.f("ck_model_usage_records_latency_ms_nonnegative"),
        ),
        sa.CheckConstraint(
            "token_input IS NULL OR token_input >= 0",
            name=op.f("ck_model_usage_records_token_input_nonnegative"),
        ),
        sa.CheckConstraint(
            "token_output IS NULL OR token_output >= 0",
            name=op.f("ck_model_usage_records_token_output_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_model_usage_records_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_model_usage_records_organization_workflow_run",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_model_usage_records_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_usage_records")),
    )
    op.create_table(
        "risk_assessments",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column(
            "risk_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("pii_detected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "prompt_injection_detected",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("weak_evidence", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "high_impact_action", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "requires_approval", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_risk_assessments_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_risk_assessments_organization_workflow_run",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_risk_assessments_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_assessments")),
    )
    op.create_table(
        "workflow_node_runs",
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("node_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "input_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "output_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name=op.f("ck_workflow_node_runs_duration_ms_nonnegative"),
        ),
        sa.CheckConstraint(
            "retry_count >= 0", name=op.f("ck_workflow_node_runs_retry_count_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name=op.f("fk_workflow_node_runs_workflow_run_id_workflow_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_node_runs")),
    )
    op.create_index(
        "ix_workflow_node_runs_node_name_status",
        "workflow_node_runs",
        ["node_name", "status"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_node_runs_workflow_run_id",
        "workflow_node_runs",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_table(
        "extracted_fields",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("field_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("source_chunk_id", sa.UUID(), nullable=True),
        sa.Column("human_edited", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_extracted_fields_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "source_chunk_id"],
            ["document_chunks.organization_id", "document_chunks.id"],
            name="fk_extracted_fields_organization_source_chunk",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_extracted_fields_organization_workflow_run",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_extracted_fields_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extracted_fields")),
    )
    op.create_table(
        "retrieved_sources",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=12, scale=8), nullable=False),
        sa.Column("retrieval_method", sa.String(length=100), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("citation_label", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint("rank >= 0", name=op.f("ck_retrieved_sources_rank_nonnegative")),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_retrieved_sources_organization_case",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "chunk_id"],
            ["document_chunks.organization_id", "document_chunks.id"],
            name="fk_retrieved_sources_organization_chunk",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_retrieved_sources_organization_document",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_retrieved_sources_organization_workflow_run",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_retrieved_sources_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retrieved_sources")),
    )
    op.create_index(
        "ix_retrieved_sources_organization_case",
        "retrieved_sources",
        ["organization_id", "case_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieved_sources_workflow_run_id",
        "retrieved_sources",
        ["workflow_run_id"],
        unique=False,
    )
    # Database triggers keep updated_at correct even when a future repository
    # updates a row outside the SQLAlchemy ORM.
    for table_name in (
        "organizations",
        "users",
        "cases",
        "documents",
        "document_chunks",
        "workflow_runs",
        "extracted_fields",
        "prompt_versions",
        "eval_datasets",
        "memory_entries",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_set_updated_at "
            f"BEFORE UPDATE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION phase4_set_updated_at()"
        )


def downgrade() -> None:
    for table_name in (
        "memory_entries",
        "eval_datasets",
        "prompt_versions",
        "extracted_fields",
        "workflow_runs",
        "document_chunks",
        "documents",
        "cases",
        "users",
        "organizations",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_set_updated_at ON {table_name}")
    op.drop_index("ix_retrieved_sources_workflow_run_id", table_name="retrieved_sources")
    op.drop_index("ix_retrieved_sources_organization_case", table_name="retrieved_sources")
    op.drop_table("retrieved_sources")
    op.drop_table("extracted_fields")
    op.drop_index("ix_workflow_node_runs_workflow_run_id", table_name="workflow_node_runs")
    op.drop_index("ix_workflow_node_runs_node_name_status", table_name="workflow_node_runs")
    op.drop_table("workflow_node_runs")
    op.drop_table("risk_assessments")
    op.drop_table("model_usage_records")
    op.drop_table("eval_results")
    op.drop_table("document_texts")
    op.drop_index("ix_document_chunks_organization_document", table_name="document_chunks")
    op.drop_index(
        "ix_document_chunks_embedding_hnsw",
        table_name="document_chunks",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    op.drop_index(
        "ix_document_chunks_content_fts", table_name="document_chunks", postgresql_using="gin"
    )
    op.drop_table("document_chunks")
    op.drop_table("approvals")
    op.drop_table("agent_messages")
    op.drop_index("ix_workflow_runs_organization_workflow_name", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_organization_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_organization_case", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_documents_organization_source_status", table_name="documents")
    op.drop_index("ix_documents_organization_case", table_name="documents")
    op.drop_index("ix_documents_checksum_sha256", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_audit_events_organization_inserted_at", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_case_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("user_roles")
    op.drop_index("ix_memory_entries_organization_user", table_name="memory_entries")
    op.drop_index("ix_memory_entries_organization_memory_scope", table_name="memory_entries")
    op.drop_table("memory_entries")
    op.drop_table("eval_runs")
    op.drop_table("eval_cases")
    op.drop_index("ix_cases_organization_status", table_name="cases")
    op.drop_index("ix_cases_organization_risk_level", table_name="cases")
    op.drop_index("ix_cases_organization_inserted_at", table_name="cases")
    op.drop_index("ix_cases_organization_case_number", table_name="cases")
    op.drop_table("cases")
    op.drop_table("users")
    op.drop_table("prompt_versions")
    op.drop_table("eval_datasets")
    op.drop_table("roles")
    op.drop_table("organizations")
    op.execute("DROP FUNCTION IF EXISTS phase4_set_updated_at()")
    # pgcrypto and vector are deliberately retained. They may predate this
    # migration or be shared by another schema, and must never be removed by a
    # project-schema rollback.
