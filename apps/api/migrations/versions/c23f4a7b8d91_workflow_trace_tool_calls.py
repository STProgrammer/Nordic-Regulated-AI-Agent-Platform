"""Add metadata-only workflow tool-call trace records and audit query indexes.

Revision ID: c23f4a7b8d91
Revises: b83a4f9d0e17
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c23f4a7b8d91"
down_revision = "b83a4f9d0e17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create one bounded trace table without changing historical workflow rows."""

    op.create_table(
        "workflow_tool_calls",
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("workflow_node_run_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "input_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_workflow_tool_calls_duration_ms_nonnegative",
        ),
        sa.CheckConstraint(
            "retry_count >= 0", name="ck_workflow_tool_calls_retry_count_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_node_run_id"],
            ["workflow_node_runs.id"],
            name="fk_workflow_tool_calls_node_run",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"], ["workflow_runs.id"], name="fk_workflow_tool_calls_workflow_run"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_tool_calls"),
    )
    op.create_index(
        "ix_workflow_tool_calls_workflow_run_started",
        "workflow_tool_calls",
        ["workflow_run_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_tool_calls_workflow_node_run_id",
        "workflow_tool_calls",
        ["workflow_node_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_organization_case_inserted_at",
        "audit_events",
        ["organization_id", "case_id", "inserted_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_organization_resource_event_inserted_at",
        "audit_events",
        ["organization_id", "resource_type", "event_type", "inserted_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only Phase-23 additive records and indexes."""

    op.drop_index(
        "ix_audit_events_organization_resource_event_inserted_at", table_name="audit_events"
    )
    op.drop_index("ix_audit_events_organization_case_inserted_at", table_name="audit_events")
    op.drop_index("ix_workflow_tool_calls_workflow_node_run_id", table_name="workflow_tool_calls")
    op.drop_index("ix_workflow_tool_calls_workflow_run_started", table_name="workflow_tool_calls")
    op.drop_table("workflow_tool_calls")
